# LLM-Agent
---
본 LLM-Agent는local 모델 또는 API를 이용한 agent 시스템을 구성하는 방식


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


# How to install
코드 작성 중 
