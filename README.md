# LLM-Agent
---
본 LLM-Agent는local 모델 또는 LLM API를 이용한 agent 시스템을 구성하는 방식

## 프로젝트 참여도
이 프로젝트는 개인 단독으로 설계 및 개발하였으며, 다음과 같은 역할을 수행하였습니다.

- FastAPI 기반 웹서버, 자동화 에이전트, Web UI 전반 개발
- LLM 응답 처리 구조 및 GUI 자동화 아키텍처 설계
- Xvfb, fluxbox, xdotool, Chrome, 등 도구 통합 및 디버깅
- LLM (Gemma 2B)과의 연동 및 코드 실행 자동화
- Docker 기반 GUI 환경 구성 및 실시간 이미지 전송 처리
- 전체 로직 테스트 및 문서화


# 인터넷 검색
https://github.com/user-attachments/assets/f75b47dd-d0fb-4642-bc06-bd2c42601444



# 코드 구현
https://github.com/user-attachments/assets/ba97a216-a3f9-4e7e-ad06-0191a1825b3c



## Agent 서버 화면

<img width="1912" height="1013" alt="Image" src="https://github.com/user-attachments/assets/be96d40c-1939-482d-b2ac-319baafb503e" />



# 시스템 구성 
---
## LLM모델 서버 <-> Linux agent 서버(Docker)

+ LLM모델 서버: 사용자 질의를 받고 답변을 생성 

+ Linux agent 서버: 사용자로부터 코드 실행 혹은 프로그램과 같은 결과 실행을 원하는 경우 대리 실행자 역할 수행
코드작성 및 실행 시 모든 언어에 대해서 조건문을 적용할 수 없으므로
대표 코드(python)를 바탕으로 타 언어 스크립트 작성
### LLM 모델 질문: python 코드로 자바에서 간단한 팝업창을 띄우는 코드를 만들어 줘

```
'''python 

java_code = """
import javax.swing.*;

public class HelloPopup {
    public static void main(String[] args) {
        JOptionPane.showMessageDialog(null, "Hello, this is a Java popup!");
    }
}
"""

with open("HelloPopup.java", "w", encoding="utf-8") as f:
    f.write(java_code.strip())

print("Java 파일 생성 완료: HelloPopup.java")
```

### 스크립트 실행 코드
```
import subprocess

# java 코드 저장
with open("HelloPopup.java", "w", encoding="utf-8") as f:
    f.write(java_code.strip())

# 자바 컴파일
subprocess.run(["javac", "HelloPopup.java"], check=True)

# 자바 실행
subprocess.run(["java", "HelloPopup"], check=True)
```
# 프로젝트 세부 내용
## LLM model 
본 환경은 Gemma-2b 모델을 사용했습니다.
(https://huggingface.co/google/gemma-2b)모델을 사용했습니다. 

## Config
현재 프로젝트는 
웹서버(8000)
LLM 서버(8001)
agent (vnc 9001) 
로 설정되어 있습니다.

### Model
This project uses the [`google/gemma-2b`](https://huggingface.co/google/gemma-2b) model under the [Gemma License](https://ai.google.dev/gemma/gemma-license).

## docker agent
pip install agent_requirements.txt

## server
pip install server_requirements.txt
