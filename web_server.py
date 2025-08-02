from fastapi import FastAPI, Form ,UploadFile, File
from fastapi.responses import HTMLResponse
from transformers import AutoTokenizer, AutoModelForCausalLM, BitsAndBytesConfig
from utils import LLMSocketServer 
import threading, shutil, os
import uvicorn
import re
import time
from collections import Counter
from fastapi.responses import JSONResponse
from fastapi.concurrency import run_in_threadpool
from fastapi.responses import RedirectResponse
import base64
from urllib.parse import quote
from konlpy.tag import Okt
from collections import Counter
import re


ts= int(time.time())


        
        
class CustomLLM():

    def __init__(self,):
        self.model=None
        self.tokenizer=None
         
    def load_model_and_tokenizer(self,model_id: str):
        bnb_config = BitsAndBytesConfig(
            load_in_8bit=True,
            llm_int8_threshold=6.0
        )
        self.tokenizer = AutoTokenizer.from_pretrained(model_id)
        self.model = AutoModelForCausalLM.from_pretrained(
            model_id,
            device_map="auto",
            quantization_config=bnb_config,
        )
        return self.tokenizer, self.model
    
    def generate_response(self,prompt: str, max_tokens: int = 1024) -> str:
        inputs = self.tokenizer(prompt, return_tensors="pt")
        inputs = {k: v.to(self.model.device) for k, v in inputs.items()}
        outputs = self.model.generate(**inputs, max_new_tokens=max_tokens,
                                        repetition_penalty=1,     # 반복 억제
                                        no_repeat_ngram_size=3)    # 3-gram 반복 금지
        decoded = self.tokenizer.decode(outputs[0], skip_special_tokens=True)
        
        return decoded[len(prompt):]    

class WebServer():
    
    def __init__(self,Socket_Server):
        self.socket_server=Socket_Server
        self.app = FastAPI()
        self.latest_image_base64=""
        self.latest_agent_message = ""
    # --- 5. HTML 템플릿 생성 ---
    def render_html(self, response: str = "") -> str:
        # return f"""
        # <!DOCTYPE html>
        # <html>
        # <head>
        # <title>LLM Chat</title>
        # </head>
        # <body>
        # <h2>LLM Agent와 대화하기</h2>
        # <div class="container">
        #     <div class="form-box">
        #     <form method="post">
        #         <textarea name="user_input" rows="10" cols="60"></textarea><br><br>
        #         <input type="submit" value="Send">
        #     </form>
        #     {response}
        #     </div>
        #     <div class="image-box">
        #     <img id="agent-img" src="/static/agent_1.png" alt="Agent 이미지">
        #     </div>
        # </div>
        # </body>
        # </html>
        # """
        
         return HTMLResponse(f"""
    <!DOCTYPE html>
    <html>
    <head>
        <title>LLM Chat</title>
    </head>
    <body>
        <h2>LLM Agent</h2>
        <div style="display: flex; justify-content: space-between; align-items: flex-start;">
            <div class="form-box" style="margin-right: 20px;">
                <form method="post" action="/chat">
                    <textarea name="user_input" rows="10" cols="60"></textarea><br><br>
                    <input type="submit" value="Send">
                </form>
            {response}
            </div>
            
            <div>
                <iframe src="/view" width="800" height="600" frameborder="0"></iframe>
            </div>
    </body>
    </html>
    """)
        
        
    def extract_code(self,text) -> str:
        """코드 블록을 추출 (Python 또는 일반 코드 블록 포함)"""
        match = re.search(r"```(?:python)?\n(.+?)```", text, re.DOTALL)
        return match.group(1).strip() if match else None

    def extract_keyword(self,text) -> str:
        #핵심단어 추출
        okt = Okt()
        cleaned_text = re.sub(r"[^\w\s]", "", text)
        nouns = okt.nouns(cleaned_text)  # 명사만 추출
        counter = Counter(nouns)
        return counter.most_common(1)[0][0]

    def extract_all(self,text) -> dict:
        """모든 결과를 한 번에 반환"""
        return {
            "code": self.extract_code(text),
            "keyword": self.extract_keyword(text)
        }
    
    def pre_proceccing_build_prompt(self, user_input: str) -> str:
        return f"""
        다음 요청이 어떤 명령에 해당하는지 판단해줘.
        가능한 응답: "web", "agent", "llm", "code"

        요청: {user_input}

        참고: 
        - '코드', '알고리즘', 'def', 'class' 등 포함 → "code"
        - '검색', '2025', '뉴스' → "web"
        - '회의록', '내 파일', '데이터셋에서' → "agent"
        - 일반 지식 질의 → "llm"

        정확한 명령 하나만 응답해줘:
                """

    def build_prompt(self, user_input: str, command: str) -> str:
        if command == "code":
            return user_input + "\n코드는 줄바꿈과 들여쓰기를 포함해서 정확히 보여줘."
        elif command == "web":
            return f"""
        "{user_input}" 에 대한 내용을 요약하시오.
            가능한 응답:
            **핵심단어:** [관련된 키워드들을 쉼표로 나열해 주세요]
            """
        elif command == "agent":
            return user_input + "\n내 로컬 문서에서 이 내용을 찾아줘."
        return user_input  # default: LLM 직접 응답

    def clean_command(self, command: str)->str:
        """
        LLM에서 받은 command 문자열을 정제하여 
        "code", "web", "agent", "llm" 중 하나로 반환.
        """
        if not isinstance(command, str):
            return ""

        # 1. 양쪽 따옴표 제거 및 공백 제거
        command = command.strip().strip('"').strip("'")

        # 2. 개행 제거 및 소문자화
        command = command.lower().strip()

        # 3. 허용된 명령어만 필터링
        allowed = {"code", "web", "agent", "llm"}
        if command in allowed:
            return command

        # 4. 혹시라도 LLM이 문장으로 출력한 경우 예: "이 요청은 code로 분류됩니다."
        match = re.search(r'\b(code|web|agent|llm)\b', command.lower())
        if match:
            return match.group(1)

        # 5. 실패 시 빈 문자열 반환
        return ""
    
def setup_routes(app: FastAPI, web_server: WebServer):
    @app.get("/", response_class=HTMLResponse)
    async def get_form(result: str = ""):
        return web_server.render_html(response=result)

    @app.post("/chat", response_class=HTMLResponse)
    async def chat(user_input: str = Form(...)):
        # 1. 명령 분류용 프롬프트
        classification_prompt = web_server.pre_proceccing_build_prompt(user_input)
        command = await run_in_threadpool(custom_llm.generate_response, classification_prompt)
        command = web_server.clean_command(command)
        # 2. 명령에 따라 응답용 프롬프트 구성
        response_prompt = web_server.build_prompt(user_input, command)

        # 3. 실제 응답 생성
        bot_reply = await run_in_threadpool(custom_llm.generate_response, response_prompt)

        # 4. 코드 또는 웹 결과라면 코드 추출
        if command in ("code", "web"):
            extracted = web_server.extract_all(bot_reply)
            if extracted.get("keyword"):
                agent_content= extracted['keyword']
            if extracted.get("code"):
                agent_content= extracted['code']    
            
            merged_message = f"__CMD__{command}\n{agent_content.strip()}"
            
            last_key = list(socket_server.agent.keys())[-1]
            web_server.socket_server.send_code(last_key, merged_message)
            
        return RedirectResponse(url="/?result=" + quote(bot_reply), status_code=303)
  
    
    # @app.post("/upload_image")
    # async def upload_image(
    #     file: UploadFile = File(...),
    #     agent_id: str = Form(...)  # ← 수정된 부분
    # ):
    #     filename = f"agent_{agent_id}.png"
    #     save_dir = "static"
    #     os.makedirs(save_dir, exist_ok=True)
    #     save_path = os.path.join(save_dir, filename)

    #     with open(save_path, "wb") as f:
    #         shutil.copyfileobj(file.file, f)

    #     return JSONResponse({"status": "ok", "filename": filename})
    @app.get("/view")
    def view_image():
        global latest_image_base64
        html_content = f"""
        <html>
        <head>
            <meta http-equiv="refresh" content="2"> <!-- 1초마다 새로고침 -->
        </head>
        <body>
            <h2>Agent 스크린샷</h2>
            <img src="data:image/png;base64,{latest_image_base64}" alt="스크린샷" width="600"/>
            <h3>Agent 응답 메시지:</h3>
        <p>{web_server.latest_agent_message}</p>
        </body>
        </html>
        """
        return HTMLResponse(content=html_content)
    
    @app.post("/upload_image")
    async def upload_image(file: UploadFile = File(...), agent_id: str = Form(...)):
        global latest_image_base64
        image_data = await file.read()
        latest_image_base64 = base64.b64encode(image_data).decode("utf-8")
        return JSONResponse({"status": "ok"})
    
    

# --- 6. FastAPI 앱 실행부 ---

if __name__=="__main__":
    model_id = "google/gemma-2b-it"
    
    latest_image_base64=" "
    custom_llm=CustomLLM()
    custom_llm.load_model_and_tokenizer(model_id)
    
    socket_server=LLMSocketServer.LLMSocketServer(host="0.0.0.0",port=8001)
    threading.Thread(target=socket_server.start, daemon=True).start()
    
    
    web_server=WebServer(socket_server)
    socket_server.web_server = web_server
    setup_routes(web_server.app,web_server)
    uvicorn.run(web_server.app, host="0.0.0.0", port=8000)
    
    
    
