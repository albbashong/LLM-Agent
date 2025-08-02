import socket
import threading
import os, io
import re
import logging
import subprocess
import json
import requests
import mss
from PIL import Image
import time
import pytesseract
import urllib.parse
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from bs4 import BeautifulSoup

logging.basicConfig(filename='app.log', level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')


class CodeExtractor:
    def extract(self, text: str) -> str:
        # LLM 응답에서 python 코드 추출
        
        if  re.search(r"```(?:python)?\n(.+?)```", text, re.DOTALL)!=None:
            match = re.search(r"```(?:python)?\n(.+?)```", text, re.DOTALL)
            return match.group(1) if match else None
        else:
            return text
        

    
class AgentMonitoring:
    
    def send_screenshot(self, agent_id, web_ip, web_port):
        try:
            while True:
                with mss.mss() as sct:
                    monitor = sct.monitors[0]
                    screenshot = sct.grab(monitor)
                    img = Image.frombytes("RGB", screenshot.size, screenshot.rgb)
                    byte_io = io.BytesIO()
                    img.save(byte_io, format="PNG")
                    byte_io.seek(0)

                    files = {"file": (f"agent_{agent_id}.png", byte_io, "image/png")}
                    data = {"agent_id": agent_id}

                    res = requests.post(
                        f"http://{web_ip}:{web_port}/upload_image", files=files, data=data
                    )
                    time.sleep(0.5)
                    if res.status_code == 200:
                        logging.info(f"[Agent {agent_id}] 스크린샷 전송 성공")
                    else:
                        logging.info(f"[Agent {agent_id}] 전송 실패: {res.status_code} - {res.text}")

        except Exception as e:
            logging.info(f"[Agent {agent_id}] 전송 중 오류 발생: {e}")
    
class CodeStorage:
    def __init__(self, base_dir="code_outputs"):
        self.base_dir = base_dir
        os.makedirs(self.base_dir, exist_ok=True)
        self.cur_files = []

    def save(self, code: str, file_name: str = None) -> str:
        if not code:
            return None
        file_name = file_name or f"code_{len(self.cur_files)}.py"
        file_path = os.path.join(self.base_dir, file_name)
        with open(file_path, "w", encoding="utf-8") as f:
            f.write(code)
        self.cur_files.append(file_path)
        return file_path

class WebSearchExecutor:
    def __init__(self, display=":1"):
        self.env = os.environ.copy()
        self.env["DISPLAY"] = display
        self.env["XDG_RUNTIME_DIR"] = "/tmp/runtime-root"  #tmp 폴더를 통한 임시폴더
        os.makedirs(self.env["XDG_RUNTIME_DIR"], exist_ok=True)
    
    def get_text(self,query):
        url = f"https://duckduckgo.com/html/?q={query}"
        headers = {
            "User-Agent": "Mozilla/5.0"
        }
        res = requests.get(url, headers=headers)
        soup = BeautifulSoup(res.text, "html.parser")
        results = [a.get_text() for a in soup.select(".result__snippet") if a.get_text()]
        return results
        
    
    def clean_ocr_text(self, text: str, k: int = 3) -> list:
        lines = text.split('\n')

        # 빈줄 제거 및 좌우 공백 제거
        lines = [line.strip() for line in lines if line.strip()]

        # 중복 제거
        seen = set()
        unique_lines = []
        for line in lines:
            if line not in seen:
                seen.add(line)
                unique_lines.append(line)

        # 상단부 내용 지우기
        keywords_to_ignore = {"더보기", "설정", "로그인", "도움말", "뉴스", "이미지"}
        filtered = [
            line for line in unique_lines
            if len(line) > 6 and not any(word in line for word in keywords_to_ignore)
        ]

        # 필터링
        regex = re.compile(r"[가-힣a-zA-Z0-9 ]{5,}")
        cleaned = [line for line in filtered if regex.search(line)]

        # 상위 k개 추출
        return cleaned[:k]
    
    
    def open_chrome_and_search(self, query: str):
        # 현재 실행중인 Chrome 종료 후 실행
        logging.info(f"검색내용: {query}")
        subprocess.run(["pkill", "-f", "chrome"])
        time.sleep(2)
        
        subprocess.Popen(
                    [
                        "google-chrome",
                        "--no-sandbox",
                        "--disable-dev-shm-usage",
                        "--disable-gpu",
                        "--disable-software-rasterizer",
                        "--no-zygote",
                        "--disable-dev-tools",
                        "--disable-features=VizDisplayCompositor"
                    ],
                    env=self.env
                )
        time.sleep(2)  # time 시간확보

        subprocess.run(
        ["xdotool", "search", "--onlyvisible", "--name", "Chrome"],
        stdout=subprocess.PIPE,
        text=True,
        check=True
    )
        
        
        # ctrl +l 을 이용한 주소창 이동
        subprocess.run(["xdotool", "key", "ctrl+l"], env=self.env)
        time.sleep(0.3)
        encoded_query = urllib.parse.quote_plus(query)
        # 검색어 입력 후 엔터
        subprocess.run(["xdotool", "type", f"https://www.google.com/search?q={encoded_query}"], env=self.env)
        time.sleep(0.5)
        
        subprocess.run(["xdotool", "key", "Return"], env=self.env)
        time.sleep(0.3)
        
        query=self.get_text(query)

        return query

class CodeRunner:
    def __init__(self, env=":1"):
        self.env = {"DISPLAY": env}

    def run_command(self,code ):
        
        proc = subprocess.run(["xdotool", "search", "--name", "llm"], capture_output=True, text=True)
        window_ids = proc.stdout.strip().split()
        for wid in window_ids:
            subprocess.run(["xdotool", "windowkill", wid])
        
        #터미널 실행
        subprocess.Popen(["lxterminal"], env=self.env)
        time.sleep(0.2)
        subprocess.run(["xdotool", "search", "--name", "llm", "windowactivate"], env=self.env)
        time.sleep(0.2) 
        
        subprocess.run(["xdotool", "type", "cd /home/llm"],env=self.env)
        time.sleep(0.2) 
        
        subprocess.run(["xdotool", "key", "Return"], env=self.env)
        time.sleep(0.2)
        
        
        # vi 를 통한 python 파일 생성
        subprocess.run(["xdotool", "type", "vi code.py"],env=self.env)
        time.sleep(0.2) 
        
        subprocess.run(["xdotool", "search", "--name", "llm", "windowactivate"], env=self.env)
        time.sleep(0.2) 
        
        
        subprocess.run(["xdotool", "key", "Return"], env=self.env)
        time.sleep(0.2)    
        
        subprocess.run(["xdotool", "type", ":set paste"], env=self.env)
        time.sleep(0.2)
        
        subprocess.run(["xdotool", "key", "Return"], env=self.env)
        time.sleep(0.2)
        
        
        subprocess.run(["xdotool", "type", "i"], env=self.env)
        time.sleep(0.2)
        
        
        if code:
            lines = code.strip().split("\n")
            for line in lines:
                print(repr(line))
                subprocess.run(["xdotool", "type", line], env=self.env)
                subprocess.run(["xdotool", "key", "Return"], env=self.env)
                time.sleep(0.1)

        else:
            print("[오류] 실행할 코드가 없습니다 (None 또는 빈 문자열)")
        
        subprocess.run(["xdotool", "key", "Escape"], env=self.env)
        time.sleep(0.2)
        subprocess.run(["xdotool", "type", ":wq!"], env=self.env)
        time.sleep(0.2)
        subprocess.run(["xdotool", "key", "Return"], env=self.env)
        time.sleep(0.2)
        
        
        print("코드 저장 성공")
    def run_python(self, file_path: str):
        try:
            result = subprocess.run(
                ["python", file_path],
                capture_output=True,
                text=True
            )
            return result.stdout, result.stderr
        except Exception as e:
            return None, str(e)


class AgentController:
    def __init__(self, extractor, storage, runner, socket,web):
        self.extractor = extractor
        self.storage = storage
        self.runner = runner
        self.socket = socket
        self.web = web 

    def process(self, text):
        
        if not text.startswith("__CMD__"):
            print("[Agent] 잘못된 메시지 형식입니다.")
            return  # ← cmd가 정의되지 않으므로 여기서 중단해야 함

        lines = text.split("\n", 1)
        cmd = lines[0][7:].strip()
        content = lines[1].strip() if len(lines)  > 1 else ""
        
        
        if cmd == "code":
            code = self.extractor.extract(content)
            # file_path = self.storage.save(code)
            # stdout, stderr = self.runner.run(file_path)
            print(f"[디버그] code 내용: {repr(code)}")
            self.runner.run_command(code)
            stdout,stderr = self.runner.run_python("/home/llm/code.py")
            result = json.dumps({"stdout": stdout, "stderr": stderr})
            self.socket.send_message(result)

        elif cmd == "web":
            result=self.web.open_chrome_and_search(content)
            self.socket.send_message(json.dumps({"web_result": result},ensure_ascii=False))
        
        


class AgentSocket:
    def __init__(self, ip_addr="127.0.0.1", port=9002):
        self.ip_addr = ip_addr
        self.port = port
        self.client_socket = None
        self.controller = None

    def set_controller(self, controller):
        self.controller = controller

    def conn_server(self):
        try:
            self.client_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self.client_socket.connect((self.ip_addr, self.port))
            print(f"Connected to {self.ip_addr}:{self.port}")
            time.sleep(0.2)
            self.send_message("[AGENT] Connected")
            thread = threading.Thread(target=self.get_message)
            thread.start()
        except Exception as e:
            print(e)
    def get_message(self):
        while True:
            try:
                data = self.client_socket.recv(4096)
                if not data:
                    print("서버 연결 종료")
                    break
                message = data.decode("utf-8")
                print(f"[서버 메시지 수신] {message}")
                if self.controller:
                    self.controller.process(message)
            except Exception as e:
                print(f"수신 오류: {e}")
                break

    def send_message(self, msg: str):
        try:
            self.client_socket.sendall(msg.encode("utf-8"))
            print(f"[송신] {msg}")
        except Exception as e:
            print(f"[송신 오류] {e}")
        
if __name__=="__main__":
    agent_monitoring=AgentMonitoring()
    th_monitoring=threading.Thread(target=agent_monitoring.send_screenshot, 
                                    args=("0","192.168.104.27","8000"))
    th_monitoring.start()
    agent_socket=AgentSocket("192.168.104.27",8001)
    
    
    extractor=CodeExtractor()
    code_storage=CodeStorage()
    runner=CodeRunner(env=":1")
    storage=CodeStorage(base_dir="/home/llm")
    web = WebSearchExecutor(display=":1")
    
    
    agent_controller=AgentController(extractor=extractor,runner=runner,
                                     storage=storage,socket=agent_socket,web=web)
    agent_socket.set_controller(agent_controller)
    agent_socket.conn_server()
    
