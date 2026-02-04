# 바라 시스템 - 작동 테스트 계획서

## 목차

- [0. 테스트 환경 준비](#0-테스트-환경-준비)
- [1. 헬스 체크 (인증 불필요)](#1-헬스-체크-인증-불필요)
- [2. 초기 설정 마법사](#2-초기-설정-마법사)
- [3. 인증 테스트](#3-인증-테스트)
- [4. 채팅 테스트 (LLM)](#4-채팅-테스트-llm)
- [5. 설정 관리](#5-설정-관리)
- [6. 플랫폼 연동](#6-플랫폼-연동)
- [7. 활동 로그](#7-활동-로그)
- [8. 알림](#8-알림)
- [9. 정보 수집](#9-정보-수집)
- [10. 슬래시 명령어](#10-슬래시-명령어)
- [11. 긴급 정지](#11-긴급-정지)
- [12. 백업/복구](#12-백업복구)
- [13. WebSocket 실시간 상태](#13-websocket-실시간-상태)
- [14. 프론트엔드 UI 테스트](#14-프론트엔드-ui-테스트)
- [15. 에러 시나리오](#15-에러-시나리오)
- [부록: 테스트 결과 기록표](#부록-테스트-결과-기록표)

---

## 0. 테스트 환경 준비

### 0.1 필수 소프트웨어

#### 소프트웨어 목록
- Python 3.11 이상
- Node.js 18 이상
- Ollama (로컬 LLM)
- Git Bash 또는 PowerShell

#### 확인 방법

**Windows PowerShell:**
```powershell
python --version
node --version
ollama --version
```

**Git Bash:**
```bash
python --version
node --version
ollama --version
```

**기대 결과:**
- Python 3.11.x 이상
- Node v18.x.x 이상
- Ollama version x.x.x

---

### 0.2 Ollama 설정

#### TC-0.2.1 Ollama 서버 실행

**테스트 방법:**

Windows PowerShell (별도 터미널):
```powershell
ollama serve
```

**기대 결과:**
```
Ollama is running at http://127.0.0.1:11434
```

#### TC-0.2.2 기본 모델 다운로드

**테스트 방법:**

```powershell
ollama pull llama3.2
```

**기대 결과:**
```
pulling manifest
pulling ... [100%]
success
```

**결과:** [ ] 성공 / [ ] 실패

#### TC-0.2.3 커스텀 성격 생성 (선택 사항)

**사전 조건:** `personalities/bara.Modelfile` 파일 존재

**테스트 방법:**

```powershell
cd D:\Taniar\Documents\Git\bara_system
ollama create bara -f personalities/bara.Modelfile
```

**기대 결과:**
```
transferring model data
using existing layer sha256:...
creating new layer sha256:...
success
```

**결과:** [ ] 성공 / [ ] 실패 / [ ] 건너뜀

---

### 0.3 백엔드 환경 구성

#### TC-0.3.1 가상 환경 생성 및 활성화

**테스트 방법:**

```powershell
cd D:\Taniar\Documents\Git\bara_system\backend
python -m venv venv
.\venv\Scripts\Activate.ps1
```

**기대 결과:**
```
(venv) PS D:\Taniar\Documents\Git\bara_system\backend>
```

**결과:** [ ] 성공 / [ ] 실패

#### TC-0.3.2 의존성 설치

**테스트 방법:**

```powershell
pip install -r requirements.txt
```

**기대 결과:**
```
Successfully installed fastapi-0.115.6 uvicorn-0.34.0 aiosqlite-0.20.0 ...
```

**결과:** [ ] 성공 / [ ] 실패

#### TC-0.3.3 환경 파일 설정

**테스트 방법:**

```powershell
# .env.example을 .env로 복사
Copy-Item .env.example .env

# config.example.json을 config.json으로 복사
Copy-Item config.example.json config.json

# 파일 확인
ls .env, config.json
```

**기대 결과:**
```
Mode     LastWriteTime         Length Name
----     -------------         ------ ----
-a----   ...                      ... .env
-a----   ...                      ... config.json
```

**결과:** [ ] 성공 / [ ] 실패

**참고:** API 키는 나중에 설정 마법사에서 입력합니다.

---

### 0.4 프론트엔드 환경 구성

#### TC-0.4.1 프론트엔드 의존성 설치

**테스트 방법:**

```powershell
cd D:\Taniar\Documents\Git\bara_system\frontend
npm install
```

**기대 결과:**
```
added 200 packages, and audited 201 packages in 15s
```

**결과:** [ ] 성공 / [ ] 실패

---

### 0.5 서버 시작

#### TC-0.5.1 백엔드 서버 시작

**사전 조건:** Ollama 서버 실행 중

**테스트 방법:**

터미널 1 (PowerShell):
```powershell
cd D:\Taniar\Documents\Git\bara_system\backend
.\venv\Scripts\Activate.ps1
uvicorn app.main:app --host 0.0.0.0 --port 5000 --reload
```

**기대 결과:**
```
INFO:     Uvicorn running on http://0.0.0.0:5000 (Press CTRL+C to quit)
INFO:     Started reloader process [xxxxx] using WatchFiles
INFO:     Started server process [xxxxx]
INFO:     Waiting for application startup.
INFO:     Application startup complete.
```

**결과:** [ ] 성공 / [ ] 실패

#### TC-0.5.2 프론트엔드 개발 서버 시작

**테스트 방법:**

터미널 2 (PowerShell, 새 창):
```powershell
cd D:\Taniar\Documents\Git\bara_system\frontend
npm run dev
```

**기대 결과:**
```
  VITE v6.0.0  ready in 500 ms

  ➜  Local:   http://localhost:5173/
  ➜  Network: use --host to expose
  ➜  press h + enter to show help
```

**결과:** [ ] 성공 / [ ] 실패

#### TC-0.5.3 프론트엔드 접속 확인

**테스트 방법:**

브라우저에서 http://localhost:5173 접속

**기대 결과:**
- 페이지가 정상 로드됨
- 설정 마법사 화면 또는 로그인 화면 표시

**결과:** [ ] 성공 / [ ] 실패

---

## 1. 헬스 체크 (인증 불필요)

### TC-1.1 기본 헬스 체크

**테스트 항목:** API 서버 정상 작동 확인

**사전 조건:** 백엔드 서버 실행 중

**테스트 방법:**

Windows PowerShell:
```powershell
curl.exe http://localhost:5000/api/health
```

Git Bash:
```bash
curl http://localhost:5000/api/health
```

**기대 결과:**
```json
{
  "status": "healthy",
  "timestamp": "2026-02-03T12:34:56.789012+00:00"
}
```

**결과:** [ ] 성공 / [ ] 실패

---

## 2. 초기 설정 마법사

### TC-2.1 설정 상태 확인

**테스트 항목:** 초기 설정 완료 여부 확인

**테스트 방법:**

Windows PowerShell:
```powershell
curl.exe http://localhost:5000/api/setup/status
```

Git Bash:
```bash
curl http://localhost:5000/api/setup/status
```

**기대 결과:**
```json
{
  "completed": false,
  "current_step": 1,
  "steps": [
    "비밀번호 설정",
    "시스템 확인",
    "모델 선택",
    "봇 설정",
    "플랫폼 연동",
    "행동 설정",
    "음성 설정",
    "설정 완료"
  ]
}
```

**결과:** [ ] 성공 / [ ] 실패

---

### TC-2.2 비밀번호 설정

**테스트 항목:** 초기 관리자 비밀번호 설정

**사전 조건:** 설정이 완료되지 않은 상태

**테스트 방법:**

Windows PowerShell:
```powershell
curl.exe -X POST http://localhost:5000/api/auth/setup-password `
  -H "Content-Type: application/json" `
  -d '{\"password\":\"test1234!\"}'
```

Git Bash:
```bash
curl -X POST http://localhost:5000/api/auth/setup-password \
  -H "Content-Type: application/json" \
  -d '{"password":"test1234!"}'
```

**기대 결과:**
```json
{
  "success": true,
  "message": "Password configured successfully."
}
```

**결과:** [ ] 성공 / [ ] 실패

**참고:** 이후 모든 테스트에서 비밀번호는 `test1234!` 사용

---

### TC-2.3 시스템 체크

**테스트 항목:** Ollama 연결 및 시스템 상태 확인

**사전 조건:** Ollama 서버 실행 중

**테스트 방법:**

Windows PowerShell:
```powershell
curl.exe http://localhost:5000/api/setup/system-check
```

Git Bash:
```bash
curl http://localhost:5000/api/setup/system-check
```

**기대 결과:**
```json
{
  "checks": [
    {
      "name": "Ollama 연결",
      "passed": true,
      "message": "Ollama 서버가 정상적으로 실행 중입니다."
    },
    {
      "name": "Python 버전",
      "passed": true,
      "message": "Python 3.11.x (권장 버전)"
    },
    {
      "name": "디스크 여유 공간",
      "passed": true,
      "message": "XX.XGB 사용 가능 (충분함)"
    }
  ]
}
```

**결과:** [ ] 성공 / [ ] 실패

---

### TC-2.4 모델 목록 조회

**테스트 항목:** Ollama에서 사용 가능한 모델 목록 확인

**사전 조건:** Ollama에 최소 1개 이상의 모델 설치됨

**테스트 방법:**

Windows PowerShell:
```powershell
curl.exe http://localhost:5000/api/setup/models
```

Git Bash:
```bash
curl http://localhost:5000/api/setup/models
```

**기대 결과:**
```json
{
  "models": [
    {
      "name": "llama3.2:latest",
      "size": 2019393189,
      "modified_at": "2026-02-03T10:00:00Z"
    },
    {
      "name": "bara:latest",
      "size": 2019393189,
      "modified_at": "2026-02-03T11:00:00Z"
    }
  ]
}
```

**결과:** [ ] 성공 / [ ] 실패

---

### TC-2.5 모델 선택

**테스트 항목:** 사용할 LLM 모델 설정

**사전 조건:** TC-2.4에서 확인한 모델 이름 사용

**테스트 방법:**

Windows PowerShell (bara 모델 사용 시):
```powershell
curl.exe -X POST http://localhost:5000/api/setup/model `
  -H "Content-Type: application/json" `
  -d '{\"model\":\"bara\"}'
```

Windows PowerShell (llama3.2 모델 사용 시):
```powershell
curl.exe -X POST http://localhost:5000/api/setup/model `
  -H "Content-Type: application/json" `
  -d '{\"model\":\"llama3.2\"}'
```

Git Bash (bara 모델 사용 시):
```bash
curl -X POST http://localhost:5000/api/setup/model \
  -H "Content-Type: application/json" \
  -d '{"model":"bara"}'
```

Git Bash (llama3.2 모델 사용 시):
```bash
curl -X POST http://localhost:5000/api/setup/model \
  -H "Content-Type: application/json" \
  -d '{"model":"llama3.2"}'
```

**기대 결과:**
```json
{
  "success": true,
  "message": "모델이 선택되었습니다."
}
```

**결과:** [ ] 성공 / [ ] 실패

**사용한 모델:** _______________

---

### TC-2.6 봇 이름 설정

**테스트 항목:** 봇의 이름 및 기본 정보 설정

**테스트 방법:**

Windows PowerShell:
```powershell
curl.exe -X POST http://localhost:5000/api/setup/bot `
  -H "Content-Type: application/json" `
  -d '{\"name\":\"바라\",\"owner_name\":\"테스터\",\"wake_words\":[\"바라야\",\"바라\"]}'
```

Git Bash:
```bash
curl -X POST http://localhost:5000/api/setup/bot \
  -H "Content-Type: application/json" \
  -d '{"name":"바라","owner_name":"테스터","wake_words":["바라야","바라"]}'
```

**기대 결과:**
```json
{
  "success": true,
  "message": "봇 설정이 저장되었습니다."
}
```

**결과:** [ ] 성공 / [ ] 실패

---

### TC-2.7 플랫폼 설정

**테스트 항목:** Moltbook 및 Botmadang 플랫폼 연동 설정

**사전 조건:**
- API 키가 없는 경우: 플랫폼 비활성화 상태로 설정 가능
- API 키가 있는 경우: 플랫폼 활성화 및 키 입력

**테스트 방법 (API 키 없이):**

Windows PowerShell:
```powershell
curl.exe -X POST http://localhost:5000/api/setup/platforms `
  -H "Content-Type: application/json" `
  -d '{\"moltbook\":{\"enabled\":false,\"api_key\":\"\"},\"botmadang\":{\"enabled\":false,\"api_key\":\"\"}}'
```

Git Bash:
```bash
curl -X POST http://localhost:5000/api/setup/platforms \
  -H "Content-Type: application/json" \
  -d '{"moltbook":{"enabled":false,"api_key":""},"botmadang":{"enabled":false,"api_key":""}}'
```

**테스트 방법 (Moltbook API 키 있을 때):**

Windows PowerShell:
```powershell
curl.exe -X POST http://localhost:5000/api/setup/platforms `
  -H "Content-Type: application/json" `
  -d '{\"moltbook\":{\"enabled\":true,\"api_key\":\"moltbook_YOUR_KEY_HERE\"},\"botmadang\":{\"enabled\":false,\"api_key\":\"\"}}'
```

Git Bash:
```bash
curl -X POST http://localhost:5000/api/setup/platforms \
  -H "Content-Type: application/json" \
  -d '{"moltbook":{"enabled":true,"api_key":"moltbook_YOUR_KEY_HERE"},"botmadang":{"enabled":false,"api_key":""}}'
```

**기대 결과 (API 키 없이):**
```json
{
  "success": true,
  "message": "플랫폼 설정이 저장되었습니다.",
  "validation": {}
}
```

**기대 결과 (API 키 있을 때):**
```json
{
  "success": true,
  "message": "플랫폼 설정이 저장되었습니다.",
  "validation": {
    "moltbook": true
  }
}
```

**결과:** [ ] 성공 / [ ] 실패

---

### TC-2.8 행동 설정

**테스트 항목:** 봇의 자동화 및 행동 파라미터 설정

**테스트 방법:**

Windows PowerShell:
```powershell
curl.exe -X POST http://localhost:5000/api/setup/behavior `
  -H "Content-Type: application/json" `
  -d '{\"auto_mode\":false,\"approval_mode\":true,\"interest_keywords\":[\"AI\",\"프로그래밍\"],\"monitoring_interval_minutes\":30}'
```

Git Bash:
```bash
curl -X POST http://localhost:5000/api/setup/behavior \
  -H "Content-Type: application/json" \
  -d '{"auto_mode":false,"approval_mode":true,"interest_keywords":["AI","프로그래밍"],"monitoring_interval_minutes":30}'
```

**기대 결과:**
```json
{
  "success": true,
  "message": "행동 설정이 저장되었습니다."
}
```

**결과:** [ ] 성공 / [ ] 실패

---

### TC-2.9 음성 설정

**테스트 항목:** 음성 인식 및 호출어 기능 설정

**테스트 방법:**

Windows PowerShell:
```powershell
curl.exe -X POST http://localhost:5000/api/setup/voice `
  -H "Content-Type: application/json" `
  -d '{\"enabled\":false,\"wake_word_engine\":\"openwakeword\",\"stt_model\":\"base\"}'
```

Git Bash:
```bash
curl -X POST http://localhost:5000/api/setup/voice \
  -H "Content-Type: application/json" \
  -d '{"enabled":false,"wake_word_engine":"openwakeword","stt_model":"base"}'
```

**기대 결과:**
```json
{
  "success": true,
  "message": "음성 설정이 저장되었습니다."
}
```

**결과:** [ ] 성공 / [ ] 실패

**참고:** 음성 기능을 사용하지 않을 경우 `enabled: false` 유지

---

### TC-2.10 설정 완료

**테스트 항목:** 설정 마법사 최종 완료

**사전 조건:** TC-2.2 ~ TC-2.9 모두 완료

**테스트 방법:**

Windows PowerShell:
```powershell
curl.exe -X POST http://localhost:5000/api/setup/complete
```

Git Bash:
```bash
curl -X POST http://localhost:5000/api/setup/complete
```

**기대 결과:**
```json
{
  "success": true,
  "message": "설정이 완료되었습니다. 이제 bara_system을 사용할 수 있습니다."
}
```

**결과:** [ ] 성공 / [ ] 실패

---

## 3. 인증 테스트

### TC-3.1 로그인

**테스트 항목:** 비밀번호를 통한 세션 생성

**사전 조건:** TC-2.2에서 설정한 비밀번호 사용 (`test1234!`)

**테스트 방법:**

Windows PowerShell:
```powershell
curl.exe -X POST http://localhost:5000/api/auth/login `
  -H "Content-Type: application/json" `
  -d '{\"password\":\"test1234!\"}' `
  -c cookie.txt
```

Git Bash:
```bash
curl -X POST http://localhost:5000/api/auth/login \
  -H "Content-Type: application/json" \
  -d '{"password":"test1234!"}' \
  -c cookie.txt
```

**기대 결과:**
```json
{
  "success": true,
  "session_token": "xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx"
}
```

**추가 확인:** `cookie.txt` 파일에 `session_token` 쿠키 저장됨

**결과:** [ ] 성공 / [ ] 실패

**참고:** 이후 인증이 필요한 모든 요청에서 `-b cookie.txt` 옵션 사용

---

### TC-3.2 인증 상태 확인

**테스트 항목:** 현재 세션의 인증 여부 확인

**사전 조건:** TC-3.1에서 로그인 완료

**테스트 방법:**

Windows PowerShell:
```powershell
curl.exe http://localhost:5000/api/auth/status `
  -b cookie.txt
```

Git Bash:
```bash
curl http://localhost:5000/api/auth/status \
  -b cookie.txt
```

**기대 결과:**
```json
{
  "authenticated": true,
  "setup_complete": true,
  "session": {
    "session_id": "xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx",
    "ip_address": "127.0.0.1",
    "created_at": "2026-02-03T12:34:56.789012+00:00",
    "expires_at": "2026-02-04T12:34:56.789012+00:00"
  }
}
```

**결과:** [ ] 성공 / [ ] 실패

---

### TC-3.3 인증 없이 접근 (거부 확인)

**테스트 항목:** 보호된 엔드포인트에 인증 없이 접근 시 거부

**테스트 방법:**

Windows PowerShell:
```powershell
curl.exe http://localhost:5000/api/settings
```

Git Bash:
```bash
curl http://localhost:5000/api/settings
```

**기대 결과:**
```json
{
  "detail": "Not authenticated"
}
```

HTTP 상태 코드: 401

**결과:** [ ] 성공 / [ ] 실패

---

### TC-3.4 로그아웃

**테스트 항목:** 세션 무효화 및 쿠키 삭제

**사전 조건:** TC-3.1에서 로그인 완료

**테스트 방법:**

Windows PowerShell:
```powershell
curl.exe -X POST http://localhost:5000/api/auth/logout `
  -b cookie.txt `
  -c cookie.txt
```

Git Bash:
```bash
curl -X POST http://localhost:5000/api/auth/logout \
  -b cookie.txt \
  -c cookie.txt
```

**기대 결과:**
```json
{
  "detail": "Logged out"
}
```

**추가 확인:** 이후 `/api/auth/status` 호출 시 `authenticated: false`

**결과:** [ ] 성공 / [ ] 실패

**참고:** 이후 테스트를 위해 다시 로그인 (TC-3.1 반복)

---

## 4. 채팅 테스트 (LLM)

### TC-4.1 비스트리밍 채팅

**테스트 항목:** LLM과의 일반 채팅 (한 번에 전체 응답 수신)

**사전 조건:**
- 로그인 완료 (cookie.txt 존재)
- Ollama 서버 실행 중

**테스트 방법:**

Windows PowerShell:
```powershell
curl.exe -X POST http://localhost:5000/api/chat `
  -H "Content-Type: application/json" `
  -d '{\"message\":\"안녕하세요, 자기소개 해주세요\"}' `
  -b cookie.txt
```

Git Bash:
```bash
curl -X POST http://localhost:5000/api/chat \
  -H "Content-Type: application/json" \
  -d '{"message":"안녕하세요, 자기소개 해주세요"}' \
  -b cookie.txt
```

**기대 결과:**
```json
{
  "response": "안녕하세요! 저는 바라입니다. AI 소셜 봇으로서 여러분의 소셜 미디어 활동을 도와드립니다...",
  "conversation_id": 2
}
```

**결과:** [ ] 성공 / [ ] 실패

**응답 시간:** ________초

---

### TC-4.2 채팅 기록 조회

**테스트 항목:** 이전 대화 내역 조회

**사전 조건:** TC-4.1에서 최소 1회 이상 채팅 완료

**테스트 방법:**

Windows PowerShell:
```powershell
curl.exe "http://localhost:5000/api/chat/history?limit=10" `
  -b cookie.txt
```

Git Bash:
```bash
curl "http://localhost:5000/api/chat/history?limit=10" \
  -b cookie.txt
```

**기대 결과:**
```json
{
  "conversations": [
    {
      "id": 1,
      "role": "user",
      "content": "안녕하세요, 자기소개 해주세요",
      "platform": "chat",
      "timestamp": "2026-02-03T12:40:00.123456+00:00"
    },
    {
      "id": 2,
      "role": "assistant",
      "content": "안녕하세요! 저는 바라입니다...",
      "platform": "chat",
      "timestamp": "2026-02-03T12:40:05.678901+00:00"
    }
  ],
  "total": 2
}
```

**결과:** [ ] 성공 / [ ] 실패

---

### TC-4.3 WebSocket 스트리밍 채팅

**테스트 항목:** WebSocket을 통한 실시간 스트리밍 채팅

**사전 조건:**
- 로그인 완료 (session_token 확보)
- WebSocket 클라이언트 도구 사용 (브라우저 콘솔 또는 wscat)

**테스트 방법 (브라우저 개발자 콘솔 사용):**

1. 브라우저에서 http://localhost:5173 접속
2. F12로 개발자 도구 열기
3. Console 탭에서 다음 코드 실행:

```javascript
// TC-3.1에서 받은 session_token 사용
const sessionToken = "YOUR_SESSION_TOKEN_HERE";
const ws = new WebSocket(`ws://localhost:5000/ws/chat?token=${sessionToken}`);

ws.onopen = () => {
  console.log("WebSocket connected");
  ws.send(JSON.stringify({message: "오늘 뭐하고 싶어?"}));
};

ws.onmessage = (event) => {
  const data = JSON.parse(event.data);
  console.log("Received:", data);

  if (data.type === "token") {
    process.stdout.write(data.content); // 토큰별 출력
  } else if (data.type === "done") {
    console.log("\n[완료]", data);
    ws.close();
  } else if (data.type === "error") {
    console.error("[에러]", data);
  }
};

ws.onerror = (error) => {
  console.error("WebSocket error:", error);
};

ws.onclose = () => {
  console.log("WebSocket closed");
};
```

**테스트 방법 (wscat 사용):**

```powershell
# wscat 설치 (처음 한 번만)
npm install -g wscat

# WebSocket 연결
wscat -c "ws://localhost:5000/ws/chat?token=YOUR_SESSION_TOKEN_HERE"

# 연결 후 메시지 전송
> {"message": "오늘 뭐하고 싶어?"}
```

**기대 결과:**

실시간으로 토큰별 스트리밍:
```json
{"type": "token", "content": "오늘"}
{"type": "token", "content": "은"}
{"type": "token", "content": " 날씨"}
{"type": "token", "content": "가"}
...
{"type": "done", "full_response": "오늘은 날씨가 좋네요! 산책이나 야외 활동을 하면 좋을 것 같아요."}
```

**결과:** [ ] 성공 / [ ] 실패

**참고:** session_token은 TC-3.1에서 받은 값 사용

---

## 5. 설정 관리

### TC-5.1 현재 설정 조회

**테스트 항목:** 전체 시스템 설정 확인

**사전 조건:** 로그인 완료

**테스트 방법:**

Windows PowerShell:
```powershell
curl.exe http://localhost:5000/api/settings `
  -b cookie.txt
```

Git Bash:
```bash
curl http://localhost:5000/api/settings \
  -b cookie.txt
```

**기대 결과:**
```json
{
  "bot": {
    "name": "바라",
    "model": "bara",
    "wake_words": ["바라야", "바라"],
    "owner_name": "테스터"
  },
  "platforms": {
    "moltbook": {
      "enabled": false,
      "base_url": "https://www.moltbook.com/api/v1"
    },
    "botmadang": {
      "enabled": false,
      "base_url": "https://botmadang.org/api/v1"
    }
  },
  "behavior": {
    "auto_mode": false,
    "approval_mode": true,
    "monitoring_interval_minutes": 30,
    "interest_keywords": ["AI", "프로그래밍"],
    ...
  },
  ...
}
```

**결과:** [ ] 성공 / [ ] 실패

---

### TC-5.2 설정 변경 (핫 리로드)

**테스트 항목:** 런타임 중 설정 변경 및 즉시 반영

**사전 조건:** 로그인 완료

**테스트 방법:**

Windows PowerShell:
```powershell
curl.exe -X PUT http://localhost:5000/api/settings `
  -H "Content-Type: application/json" `
  -d '{\"section\":\"behavior\",\"data\":{\"monitoring_interval_minutes\":15}}' `
  -b cookie.txt
```

Git Bash:
```bash
curl -X PUT http://localhost:5000/api/settings \
  -H "Content-Type: application/json" \
  -d '{"section":"behavior","data":{"monitoring_interval_minutes":15}}' \
  -b cookie.txt
```

**기대 결과:**
```json
{
  "detail": "Section 'behavior' updated successfully",
  "current": {
    "bot": {...},
    "behavior": {
      "monitoring_interval_minutes": 15,
      ...
    },
    ...
  }
}
```

**추가 확인:** `config.json` 파일 열어서 `monitoring_interval_minutes` 값이 15로 변경되었는지 확인

**결과:** [ ] 성공 / [ ] 실패

---

### TC-5.3 설정 변경 이력

**테스트 항목:** 설정 변경 스냅샷 이력 조회

**사전 조건:** TC-5.2에서 최소 1회 이상 설정 변경

**테스트 방법:**

Windows PowerShell:
```powershell
curl.exe "http://localhost:5000/api/settings/history?limit=5" `
  -b cookie.txt
```

Git Bash:
```bash
curl "http://localhost:5000/api/settings/history?limit=5" \
  -b cookie.txt
```

**기대 결과:**
```json
{
  "items": [
    {
      "id": 2,
      "config_json": "{\"bot\":{...},\"behavior\":{\"monitoring_interval_minutes\":15,...},...}",
      "timestamp": "2026-02-03T13:00:00.000000+00:00"
    },
    {
      "id": 1,
      "config_json": "{\"bot\":{...},\"behavior\":{\"monitoring_interval_minutes\":30,...},...}",
      "timestamp": "2026-02-03T12:50:00.000000+00:00"
    }
  ],
  "total": 2
}
```

**결과:** [ ] 성공 / [ ] 실패

---

## 6. 플랫폼 연동

### TC-6.1 플랫폼 목록

**테스트 항목:** 등록된 플랫폼의 상태 확인

**사전 조건:** 로그인 완료

**테스트 방법:**

Windows PowerShell:
```powershell
curl.exe http://localhost:5000/api/platforms `
  -b cookie.txt
```

Git Bash:
```bash
curl http://localhost:5000/api/platforms \
  -b cookie.txt
```

**기대 결과:**
```json
{
  "moltbook": {
    "enabled": false,
    "has_credentials": false,
    "base_url": "https://www.moltbook.com/api/v1"
  },
  "botmadang": {
    "enabled": false,
    "has_credentials": false,
    "base_url": "https://botmadang.org/api/v1"
  }
}
```

**결과:** [ ] 성공 / [ ] 실패

---

### TC-6.2 API 키 검증 (Moltbook)

**테스트 항목:** Moltbook API 키 유효성 검증

**사전 조건:**
- 로그인 완료
- 유효한 Moltbook API 키 보유

**테스트 방법:**

Windows PowerShell:
```powershell
curl.exe -X POST http://localhost:5000/api/platforms/validate `
  -H "Content-Type: application/json" `
  -d '{\"platform\":\"moltbook\"}' `
  -b cookie.txt
```

Git Bash:
```bash
curl -X POST http://localhost:5000/api/platforms/validate \
  -H "Content-Type: application/json" \
  -d '{"platform":"moltbook"}' \
  -b cookie.txt
```

**기대 결과 (API 키 유효):**
```json
{
  "platform": "moltbook",
  "valid": true
}
```

**기대 결과 (API 키 없음 또는 무효):**
```json
{
  "platform": "moltbook",
  "valid": false
}
```

**결과:** [ ] 성공 / [ ] 실패 / [ ] 건너뜀 (API 키 없음)

---

### TC-6.3 Botmadang 에이전트 등록

**테스트 항목:** Botmadang 플랫폼에 새 에이전트 등록

**사전 조건:**
- 로그인 완료
- 유효한 Botmadang API 키 보유

**테스트 방법:**

Windows PowerShell:
```powershell
curl.exe -X POST http://localhost:5000/api/platforms/botmadang/register `
  -H "Content-Type: application/json" `
  -d '{\"name\":\"바라_테스트\",\"description\":\"테스트용 바라 봇입니다.\"}' `
  -b cookie.txt
```

Git Bash:
```bash
curl -X POST http://localhost:5000/api/platforms/botmadang/register \
  -H "Content-Type: application/json" \
  -d '{"name":"바라_테스트","description":"테스트용 바라 봇입니다."}' \
  -b cookie.txt
```

**기대 결과 (성공):**
```json
{
  "success": true,
  "claim_url": "https://botmadang.org/claim/xxxxxxxxxxxx",
  "verification_code": "ABCD-1234"
}
```

**추가 작업:** X/Twitter에서 verification_code를 포함한 트윗 작성 후 claim_url 방문

**결과:** [ ] 성공 / [ ] 실패 / [ ] 건너뜀 (API 키 없음)

---

## 7. 활동 로그

### TC-7.1 활동 목록 조회

**테스트 항목:** 봇의 모든 활동 기록 조회

**사전 조건:** 로그인 완료

**테스트 방법:**

Windows PowerShell:
```powershell
curl.exe "http://localhost:5000/api/activities?limit=20" `
  -b cookie.txt
```

Git Bash:
```bash
curl "http://localhost:5000/api/activities?limit=20" \
  -b cookie.txt
```

**기대 결과 (활동 없는 경우):**
```json
{
  "items": [],
  "total": 0,
  "limit": 20,
  "offset": 0
}
```

**기대 결과 (활동 있는 경우):**
```json
{
  "items": [
    {
      "id": 1,
      "platform": "moltbook",
      "type": "comment",
      "target_id": "post_123",
      "content": "좋은 글이네요!",
      "status": "completed",
      "timestamp": "2026-02-03T13:10:00.000000+00:00"
    }
  ],
  "total": 1,
  "limit": 20,
  "offset": 0
}
```

**결과:** [ ] 성공 / [ ] 실패

---

### TC-7.2 활동 상세 조회

**테스트 항목:** 특정 활동의 상세 정보 조회

**사전 조건:**
- 로그인 완료
- TC-7.1에서 활동 목록에 최소 1개 이상의 활동 존재

**테스트 방법:**

Windows PowerShell (activity_id는 TC-7.1에서 확인한 값 사용):
```powershell
curl.exe http://localhost:5000/api/activities/1 `
  -b cookie.txt
```

Git Bash:
```bash
curl http://localhost:5000/api/activities/1 \
  -b cookie.txt
```

**기대 결과:**
```json
{
  "id": 1,
  "platform": "moltbook",
  "type": "comment",
  "target_id": "post_123",
  "content": "좋은 글이네요!",
  "status": "completed",
  "metadata": {
    "post_title": "AI의 미래",
    "community": "technology"
  },
  "timestamp": "2026-02-03T13:10:00.000000+00:00"
}
```

**결과:** [ ] 성공 / [ ] 실패 / [ ] 건너뜀 (활동 없음)

---

### TC-7.3 플랫폼별 활동 필터링

**테스트 항목:** 특정 플랫폼의 활동만 조회

**사전 조건:** 로그인 완료

**테스트 방법:**

Windows PowerShell:
```powershell
curl.exe "http://localhost:5000/api/activities?platform=moltbook&limit=20" `
  -b cookie.txt
```

Git Bash:
```bash
curl "http://localhost:5000/api/activities?platform=moltbook&limit=20" \
  -b cookie.txt
```

**기대 결과:**
```json
{
  "items": [
    {
      "id": 1,
      "platform": "moltbook",
      ...
    }
  ],
  "total": 1,
  "limit": 20,
  "offset": 0
}
```

**결과:** [ ] 성공 / [ ] 실패

---

## 8. 알림

### TC-8.1 알림 목록

**테스트 항목:** 수신된 알림 목록 조회

**사전 조건:** 로그인 완료

**테스트 방법:**

Windows PowerShell:
```powershell
curl.exe "http://localhost:5000/api/notifications?limit=20" `
  -b cookie.txt
```

Git Bash:
```bash
curl "http://localhost:5000/api/notifications?limit=20" \
  -b cookie.txt
```

**기대 결과 (알림 없는 경우):**
```json
{
  "items": [],
  "total": 0
}
```

**기대 결과 (알림 있는 경우):**
```json
{
  "items": [
    {
      "id": 1,
      "platform": "moltbook",
      "type": "reply",
      "source_id": "comment_456",
      "content": "답글이 달렸습니다.",
      "is_read": false,
      "timestamp": "2026-02-03T13:20:00.000000+00:00"
    }
  ],
  "total": 1
}
```

**결과:** [ ] 성공 / [ ] 실패

---

### TC-8.2 미읽음 알림 필터링

**테스트 항목:** 읽지 않은 알림만 조회

**사전 조건:** 로그인 완료

**테스트 방법:**

Windows PowerShell:
```powershell
curl.exe "http://localhost:5000/api/notifications?unread=true&limit=20" `
  -b cookie.txt
```

Git Bash:
```bash
curl "http://localhost:5000/api/notifications?unread=true&limit=20" \
  -b cookie.txt
```

**기대 결과:**
```json
{
  "items": [
    {
      "id": 1,
      "is_read": false,
      ...
    }
  ],
  "total": 1
}
```

**결과:** [ ] 성공 / [ ] 실패

---

### TC-8.3 알림 읽음 처리

**테스트 항목:** 특정 알림을 읽음으로 표시

**사전 조건:**
- 로그인 완료
- TC-8.1에서 최소 1개 이상의 알림 존재

**테스트 방법:**

Windows PowerShell (notification_id는 TC-8.1에서 확인한 값 사용):
```powershell
curl.exe -X POST http://localhost:5000/api/notifications/1/read `
  -b cookie.txt
```

Git Bash:
```bash
curl -X POST http://localhost:5000/api/notifications/1/read \
  -b cookie.txt
```

**기대 결과:**
```json
{
  "detail": "Notification marked as read"
}
```

**추가 확인:** TC-8.1 다시 실행하여 해당 알림의 `is_read: true` 확인

**결과:** [ ] 성공 / [ ] 실패 / [ ] 건너뜀 (알림 없음)

---

## 9. 정보 수집

### TC-9.1 수집 정보 목록

**테스트 항목:** 봇이 수집한 정보 조회

**사전 조건:** 로그인 완료

**테스트 방법:**

Windows PowerShell:
```powershell
curl.exe "http://localhost:5000/api/collected-info?limit=20" `
  -b cookie.txt
```

Git Bash:
```bash
curl "http://localhost:5000/api/collected-info?limit=20" \
  -b cookie.txt
```

**기대 결과 (수집 정보 없는 경우):**
```json
{
  "items": [],
  "total": 0,
  "limit": 20,
  "offset": 0
}
```

**기대 결과 (수집 정보 있는 경우):**
```json
{
  "items": [
    {
      "id": 1,
      "category": "technology",
      "content": "AI 관련 흥미로운 정보",
      "source": "https://example.com/article",
      "is_bookmarked": false,
      "timestamp": "2026-02-03T13:30:00.000000+00:00"
    }
  ],
  "total": 1,
  "limit": 20,
  "offset": 0
}
```

**결과:** [ ] 성공 / [ ] 실패

---

### TC-9.2 카테고리 목록

**테스트 항목:** 수집된 정보의 모든 카테고리 조회

**사전 조건:** 로그인 완료

**테스트 방법:**

Windows PowerShell:
```powershell
curl.exe http://localhost:5000/api/collected-info/categories `
  -b cookie.txt
```

Git Bash:
```bash
curl http://localhost:5000/api/collected-info/categories \
  -b cookie.txt
```

**기대 결과 (카테고리 없는 경우):**
```json
{
  "categories": []
}
```

**기대 결과 (카테고리 있는 경우):**
```json
{
  "categories": ["technology", "news", "programming"]
}
```

**결과:** [ ] 성공 / [ ] 실패

---

### TC-9.3 검색

**테스트 항목:** 키워드로 수집 정보 검색

**사전 조건:** 로그인 완료

**테스트 방법:**

Windows PowerShell:
```powershell
curl.exe "http://localhost:5000/api/collected-info?q=AI&limit=20" `
  -b cookie.txt
```

Git Bash:
```bash
curl "http://localhost:5000/api/collected-info?q=AI&limit=20" \
  -b cookie.txt
```

**기대 결과:**
```json
{
  "items": [
    {
      "id": 1,
      "content": "AI 관련 흥미로운 정보",
      ...
    }
  ],
  "total": 1,
  "limit": 20,
  "offset": 0
}
```

**결과:** [ ] 성공 / [ ] 실패

---

### TC-9.4 북마크 토글

**테스트 항목:** 특정 정보를 북마크 추가/해제

**사전 조건:**
- 로그인 완료
- TC-9.1에서 최소 1개 이상의 수집 정보 존재

**테스트 방법:**

Windows PowerShell (item_id는 TC-9.1에서 확인한 값 사용):
```powershell
curl.exe -X POST http://localhost:5000/api/collected-info/1/bookmark `
  -b cookie.txt
```

Git Bash:
```bash
curl -X POST http://localhost:5000/api/collected-info/1/bookmark \
  -b cookie.txt
```

**기대 결과:**
```json
{
  "id": 1,
  "bookmarked": true
}
```

**추가 확인:** 같은 요청 다시 실행 시 `bookmarked: false`로 토글됨

**결과:** [ ] 성공 / [ ] 실패 / [ ] 건너뜀 (수집 정보 없음)

---

## 10. 슬래시 명령어

### TC-10.1 상태 명령

**테스트 항목:** `/status` 명령으로 시스템 상태 확인

**사전 조건:** 로그인 완료

**테스트 방법:**

Windows PowerShell:
```powershell
curl.exe -X POST http://localhost:5000/api/commands `
  -H "Content-Type: application/json" `
  -d '{\"command\":\"/status\"}' `
  -b cookie.txt
```

Git Bash:
```bash
curl -X POST http://localhost:5000/api/commands \
  -H "Content-Type: application/json" \
  -d '{"command":"/status"}' \
  -b cookie.txt
```

**기대 결과:**
```json
{
  "success": true,
  "command": "status",
  "result": {
    "scheduler": {
      "is_running": false,
      "next_feed_monitor": null,
      "next_notification_check": null
    },
    "kill_switch_active": false,
    "queue_sizes": {
      "post": 0,
      "comment": 0,
      "upvote": 0
    },
    "platforms": {
      "moltbook": {
        "enabled": false,
        ...
      },
      "botmadang": {
        "enabled": false,
        ...
      }
    }
  }
}
```

**결과:** [ ] 성공 / [ ] 실패

---

### TC-10.2 정지 명령

**테스트 항목:** `/stop` 명령으로 긴급 정지 활성화

**사전 조건:** 로그인 완료

**테스트 방법:**

Windows PowerShell:
```powershell
curl.exe -X POST http://localhost:5000/api/commands `
  -H "Content-Type: application/json" `
  -d '{\"command\":\"/stop\"}' `
  -b cookie.txt
```

Git Bash:
```bash
curl -X POST http://localhost:5000/api/commands \
  -H "Content-Type: application/json" \
  -d '{"command":"/stop"}' \
  -b cookie.txt
```

**기대 결과:**
```json
{
  "success": true,
  "command": "stop",
  "result": {
    "activated": true
  }
}
```

**추가 확인:** 백엔드 디렉토리에 `STOP_BOT` 파일 생성됨

**결과:** [ ] 성공 / [ ] 실패

**참고:** 다음 테스트를 위해 TC-11.3으로 긴급 정지 해제 필요

---

### TC-10.3 검색 명령

**테스트 항목:** `/search` 명령으로 플랫폼 게시물 검색

**사전 조건:**
- 로그인 완료
- Moltbook API 키 설정 및 활성화

**테스트 방법:**

Windows PowerShell:
```powershell
curl.exe -X POST http://localhost:5000/api/commands `
  -H "Content-Type: application/json" `
  -d '{\"command\":\"/search\",\"args\":{\"query\":\"AI\",\"platform\":\"moltbook\",\"semantic\":false}}' `
  -b cookie.txt
```

Git Bash:
```bash
curl -X POST http://localhost:5000/api/commands \
  -H "Content-Type: application/json" \
  -d '{"command":"/search","args":{"query":"AI","platform":"moltbook","semantic":false}}' \
  -b cookie.txt
```

**기대 결과:**
```json
{
  "success": true,
  "command": "search",
  "result": {
    "query": "AI",
    "platform": "moltbook",
    "count": 10,
    "posts": [
      {
        "post_id": "123",
        "title": "AI의 미래",
        "author": "user123",
        "url": "https://www.moltbook.com/posts/123",
        "score": 42
      },
      ...
    ]
  }
}
```

**결과:** [ ] 성공 / [ ] 실패 / [ ] 건너뜀 (API 키 없음)

---

## 11. 긴급 정지

### TC-11.1 긴급 정지 활성화

**테스트 항목:** 긴급 정지 버튼으로 모든 자동화 중단

**사전 조건:** 로그인 완료

**테스트 방법:**

Windows PowerShell:
```powershell
curl.exe -X POST http://localhost:5000/api/emergency-stop `
  -b cookie.txt
```

Git Bash:
```bash
curl -X POST http://localhost:5000/api/emergency-stop \
  -b cookie.txt
```

**기대 결과:**
```json
{
  "detail": "Emergency stop activated",
  "active": true
}
```

**추가 확인:**
- 백엔드 디렉토리에 `STOP_BOT` 파일 생성됨
- 백엔드 콘솔에 경고 로그 출력됨

**결과:** [ ] 성공 / [ ] 실패

---

### TC-11.2 긴급 정지 상태 확인

**테스트 항목:** 현재 긴급 정지 상태 조회

**사전 조건:** TC-11.1에서 긴급 정지 활성화

**테스트 방법:**

Windows PowerShell:
```powershell
curl.exe http://localhost:5000/api/emergency-status `
  -b cookie.txt
```

Git Bash:
```bash
curl http://localhost:5000/api/emergency-status \
  -b cookie.txt
```

**기대 결과:**
```json
{
  "active": true,
  "scheduler_running": false,
  "scheduler_state": {
    "is_running": false,
    "next_feed_monitor": null,
    "next_notification_check": null
  }
}
```

**결과:** [ ] 성공 / [ ] 실패

---

### TC-11.3 긴급 정지 해제

**테스트 항목:** 긴급 정지 해제 및 서비스 재개

**사전 조건:** TC-11.1에서 긴급 정지 활성화

**테스트 방법:**

Windows PowerShell:
```powershell
curl.exe -X POST http://localhost:5000/api/emergency-resume `
  -b cookie.txt
```

Git Bash:
```bash
curl -X POST http://localhost:5000/api/emergency-resume \
  -b cookie.txt
```

**기대 결과:**
```json
{
  "detail": "Emergency stop deactivated, services restarted",
  "active": false
}
```

**추가 확인:**
- `STOP_BOT` 파일 삭제됨
- 백엔드 콘솔에 재시작 로그 출력됨

**결과:** [ ] 성공 / [ ] 실패

---

## 12. 백업/복구

### TC-12.1 백업 내보내기

**테스트 항목:** 전체 데이터베이스 및 설정 백업

**사전 조건:** 로그인 완료

**테스트 방법:**

Windows PowerShell:
```powershell
curl.exe -X POST http://localhost:5000/api/backup/export `
  -b cookie.txt `
  -o backup.json
```

Git Bash:
```bash
curl -X POST http://localhost:5000/api/backup/export \
  -b cookie.txt \
  -o backup.json
```

**기대 결과:**
- `backup.json` 파일 생성됨
- 파일 내용에 `tables`, `config`, `metadata` 포함

**추가 확인:** 백엔드 `backups/` 디렉토리에 `backup_YYYYMMDD_HHMMSS.json` 파일 생성됨

**결과:** [ ] 성공 / [ ] 실패

**백업 파일 크기:** ________KB

---

### TC-12.2 백업 가져오기

**테스트 항목:** 백업 파일로부터 데이터 복구

**사전 조건:**
- 로그인 완료
- TC-12.1에서 생성한 `backup.json` 파일 존재

**테스트 방법:**

Windows PowerShell:
```powershell
# backup.json 파일 내용을 읽어서 전송
$backup = Get-Content backup.json -Raw
curl.exe -X POST http://localhost:5000/api/backup/import `
  -H "Content-Type: application/json" `
  -d $backup `
  -b cookie.txt
```

Git Bash:
```bash
curl -X POST http://localhost:5000/api/backup/import \
  -H "Content-Type: application/json" \
  -d @backup.json \
  -b cookie.txt
```

**기대 결과:**
```json
{
  "detail": "Backup imported successfully"
}
```

**결과:** [ ] 성공 / [ ] 실패

**참고:** 백업 가져오기는 기존 데이터를 덮어쓸 수 있으므로 주의

---

## 13. WebSocket 실시간 상태

### TC-13.1 상태 WebSocket 연결

**테스트 항목:** WebSocket을 통한 실시간 상태 업데이트 수신

**사전 조건:**
- 로그인 완료 (session_token 확보)
- WebSocket 클라이언트 도구 사용

**테스트 방법 (브라우저 개발자 콘솔 사용):**

```javascript
const sessionToken = "YOUR_SESSION_TOKEN_HERE";
const ws = new WebSocket(`ws://localhost:5000/ws/status?token=${sessionToken}`);

ws.onopen = () => {
  console.log("Status WebSocket connected");
};

ws.onmessage = (event) => {
  const data = JSON.parse(event.data);
  console.log("Status update:", data);
};

ws.onerror = (error) => {
  console.error("WebSocket error:", error);
};

ws.onclose = () => {
  console.log("WebSocket closed");
};
```

**테스트 방법 (wscat 사용):**

```powershell
wscat -c "ws://localhost:5000/ws/status?token=YOUR_SESSION_TOKEN_HERE"
```

**기대 결과:**

연결 직후 즉시 `state_sync` 이벤트 수신:
```json
{
  "type": "state_sync",
  "data": {
    "scheduler_running": false,
    "kill_switch_active": false,
    "auto_mode": false,
    "approval_mode": true
  }
}
```

**결과:** [ ] 성공 / [ ] 실패

---

### TC-13.2 설정 변경 이벤트 수신

**테스트 항목:** 다른 클라이언트의 설정 변경 시 실시간 알림

**사전 조건:** TC-13.1에서 WebSocket 연결 유지 중

**테스트 방법:**

1. WebSocket 연결 유지
2. 다른 터미널에서 TC-5.2 실행 (설정 변경)
3. WebSocket에서 이벤트 수신 확인

**기대 결과:**

WebSocket에서 `config_changed` 이벤트 수신:
```json
{
  "type": "config_changed",
  "data": {
    "section": "behavior",
    "new_config": {
      "monitoring_interval_minutes": 15,
      ...
    }
  }
}
```

**결과:** [ ] 성공 / [ ] 실패

---

### TC-13.3 긴급 정지 이벤트 수신

**테스트 항목:** 긴급 정지 활성화 시 실시간 알림

**사전 조건:** TC-13.1에서 WebSocket 연결 유지 중

**테스트 방법:**

1. WebSocket 연결 유지
2. 다른 터미널에서 TC-11.1 실행 (긴급 정지 활성화)
3. WebSocket에서 이벤트 수신 확인

**기대 결과:**

WebSocket에서 `emergency_stop` 이벤트 수신:
```json
{
  "type": "emergency_stop",
  "data": {
    "active": true,
    "source": "api"
  }
}
```

**결과:** [ ] 성공 / [ ] 실패

**참고:** TC-11.3으로 긴급 정지 해제 필요

---

## 14. 프론트엔드 UI 테스트

### TC-14.1 초기 접속 → 설정 마법사

**테스트 항목:** 처음 접속 시 설정 마법사 표시

**사전 조건:**
- 설정이 완료되지 않은 상태 (TC-2 이전)
- 프론트엔드 서버 실행 중

**테스트 방법:**

1. 브라우저에서 http://localhost:5173 접속
2. 화면 확인

**기대 결과:**
- 설정 마법사 화면 표시
- "비밀번호 설정" 단계 표시
- 단계 진행 표시기 (1/8)

**결과:** [ ] 성공 / [ ] 실패

---

### TC-14.2 로그인 화면

**테스트 항목:** 설정 완료 후 로그인 화면 표시

**사전 조건:**
- TC-2 완료 (설정 완료)
- 프론트엔드 서버 실행 중

**테스트 방법:**

1. 브라우저에서 http://localhost:5173 접속
2. 로그인 화면 확인
3. 비밀번호 입력: `test1234!`
4. "로그인" 버튼 클릭

**기대 결과:**
- 로그인 화면 표시
- 비밀번호 입력 후 메인 화면으로 이동
- 상단에 "바라" 봇 이름 표시

**결과:** [ ] 성공 / [ ] 실패

---

### TC-14.3 채팅 탭

**테스트 항목:** 채팅 인터페이스 정상 작동

**사전 조건:** TC-14.2에서 로그인 완료

**테스트 방법:**

1. 좌측 메뉴에서 "채팅" 탭 클릭
2. 메시지 입력창에 "안녕하세요" 입력
3. 전송 버튼 클릭 또는 Enter 키 입력
4. 응답 확인

**기대 결과:**
- 채팅 인터페이스 표시
- 입력한 메시지가 오른쪽에 표시 (사용자 메시지)
- LLM 응답이 왼쪽에 표시 (봇 메시지)
- 스트리밍 방식으로 토큰별 출력 (선택적)

**결과:** [ ] 성공 / [ ] 실패

---

### TC-14.4 활동 로그 탭

**테스트 항목:** 활동 로그 화면 표시 및 필터링

**사전 조건:** TC-14.2에서 로그인 완료

**테스트 방법:**

1. 좌측 메뉴에서 "활동" 탭 클릭
2. 활동 목록 확인
3. 플랫폼 필터 (Moltbook, Botmadang) 클릭
4. 활동 타입 필터 (댓글, 게시물, 추천) 클릭

**기대 결과:**
- 활동 로그 화면 표시
- 시간 역순으로 활동 목록 표시
- 필터 적용 시 목록 갱신
- 활동 없는 경우 "활동 없음" 메시지

**결과:** [ ] 성공 / [ ] 실패

---

### TC-14.5 정보 수집 탭

**테스트 항목:** 수집된 정보 화면 표시 및 북마크

**사전 조건:** TC-14.2에서 로그인 완료

**테스트 방법:**

1. 좌측 메뉴에서 "정보" 탭 클릭
2. 수집 정보 목록 확인
3. 검색창에 키워드 입력 후 검색
4. 항목의 북마크 아이콘 클릭

**기대 결과:**
- 정보 수집 화면 표시
- 카테고리별 탭 표시
- 검색 결과 즉시 반영
- 북마크 토글 시 아이콘 변경

**결과:** [ ] 성공 / [ ] 실패

---

### TC-14.6 설정 탭

**테스트 항목:** 설정 화면에서 실시간 설정 변경

**사전 조건:** TC-14.2에서 로그인 완료

**테스트 방법:**

1. 좌측 메뉴에서 "설정" 탭 클릭
2. "행동" 섹션 확장
3. "모니터링 주기" 값 변경 (30 → 15)
4. "저장" 버튼 클릭
5. 성공 메시지 확인

**기대 결과:**
- 설정 화면 표시
- 모든 설정 섹션 표시 (봇, 플랫폼, 행동, 음성, 보안, UI)
- 값 변경 후 저장 시 성공 메시지
- 페이지 새로고침 시 변경된 값 유지

**결과:** [ ] 성공 / [ ] 실패

---

### TC-14.7 긴급 정지 버튼

**테스트 항목:** UI에서 긴급 정지 활성화/해제

**사전 조건:** TC-14.2에서 로그인 완료

**테스트 방법:**

1. 상단 헤더의 긴급 정지 버튼 클릭
2. 확인 대화상자에서 "확인" 클릭
3. 버튼 상태 변경 확인
4. 다시 클릭하여 해제

**기대 결과:**
- 긴급 정지 버튼 표시 (빨간색 또는 경고 스타일)
- 클릭 시 확인 대화상자 표시
- 활성화 시 버튼 색상/텍스트 변경
- 활성화 상태에서 자동화 기능 비활성화
- 해제 시 원래 상태로 복원

**결과:** [ ] 성공 / [ ] 실패

---

### TC-14.8 연결 상태 표시기 (WebSocket)

**테스트 항목:** 실시간 연결 상태 표시

**사전 조건:** TC-14.2에서 로그인 완료

**테스트 방법:**

1. 화면 우측 상단 또는 하단의 연결 상태 표시기 확인
2. 백엔드 서버 중단 (Ctrl+C)
3. 연결 상태 표시기 변경 확인
4. 백엔드 서버 재시작
5. 자동 재연결 확인

**기대 결과:**
- 연결됨: 녹색 점 또는 "연결됨" 텍스트
- 연결 끊김: 빨간색 점 또는 "연결 끊김" 텍스트
- 재연결 중: 노란색 점 또는 "재연결 중..." 텍스트
- 자동 재연결 성공 시 녹색으로 변경

**결과:** [ ] 성공 / [ ] 실패

---

## 15. 에러 시나리오

### TC-15.1 Ollama 미실행 시

**테스트 항목:** Ollama 서버가 실행되지 않은 상태에서 헬스 체크

**사전 조건:**
- Ollama 서버 중지 (ollama serve 프로세스 종료)
- 백엔드 서버 실행 중

**테스트 방법:**

Windows PowerShell:
```powershell
curl.exe http://localhost:5000/api/health
```

Git Bash:
```bash
curl http://localhost:5000/api/health
```

**기대 결과:**
```json
{
  "status": "healthy",
  "timestamp": "2026-02-03T14:00:00.000000+00:00"
}
```

**참고:**
- `/api/health`는 항상 healthy 반환
- Ollama 연결 확인은 `/api/setup/system-check` 사용

**추가 테스트 (시스템 체크):**

```powershell
curl.exe http://localhost:5000/api/setup/system-check
```

**기대 결과 (Ollama 미실행):**
```json
{
  "checks": [
    {
      "name": "Ollama 연결",
      "passed": false,
      "message": "Ollama 서버에 연결할 수 없습니다."
    },
    ...
  ]
}
```

**결과:** [ ] 성공 / [ ] 실패

**복구:** Ollama 서버 재시작 (`ollama serve`)

---

### TC-15.2 잘못된 비밀번호 로그인

**테스트 항목:** 틀린 비밀번호로 로그인 시도

**사전 조건:** 설정 완료 (비밀번호: `test1234!`)

**테스트 방법:**

Windows PowerShell:
```powershell
curl.exe -X POST http://localhost:5000/api/auth/login `
  -H "Content-Type: application/json" `
  -d '{\"password\":\"wrongpassword\"}'
```

Git Bash:
```bash
curl -X POST http://localhost:5000/api/auth/login \
  -H "Content-Type: application/json" \
  -d '{"password":"wrongpassword"}'
```

**기대 결과:**
```json
{
  "success": false,
  "error": "Invalid password"
}
```

**결과:** [ ] 성공 / [ ] 실패

---

### TC-15.3 잠금 (5회 실패 후)

**테스트 항목:** 연속 5회 로그인 실패 시 계정 잠금

**사전 조건:** 설정 완료

**테스트 방법:**

TC-15.2를 5번 연속 실행

**기대 결과 (5번째 시도):**
```json
{
  "success": false,
  "error": "Too many failed attempts. Please try again later."
}
```

**추가 확인:** 올바른 비밀번호로 로그인 시도 시에도 같은 에러 발생

**결과:** [ ] 성공 / [ ] 실패

**참고:**
- 잠금 시간은 `config.json`의 `web_security.lockout_minutes` (기본 5분)
- 테스트 후 5분 대기 또는 백엔드 재시작

---

### TC-15.4 잘못된 API 키

**테스트 항목:** 유효하지 않은 API 키로 플랫폼 검증

**사전 조건:** 로그인 완료

**테스트 방법:**

Windows PowerShell:
```powershell
curl.exe -X POST http://localhost:5000/api/platforms/validate `
  -H "Content-Type: application/json" `
  -d '{\"platform\":\"moltbook\"}' `
  -b cookie.txt
```

Git Bash:
```bash
curl -X POST http://localhost:5000/api/platforms/validate \
  -H "Content-Type: application/json" \
  -d '{"platform":"moltbook"}' \
  -b cookie.txt
```

**기대 결과 (API 키 없거나 잘못됨):**
```json
{
  "platform": "moltbook",
  "valid": false
}
```

**결과:** [ ] 성공 / [ ] 실패

---

### TC-15.5 존재하지 않는 모델 선택

**테스트 항목:** Ollama에 없는 모델을 선택

**사전 조건:** Ollama 서버 실행 중

**테스트 방법:**

Windows PowerShell:
```powershell
curl.exe -X POST http://localhost:5000/api/setup/model `
  -H "Content-Type: application/json" `
  -d '{\"model\":\"nonexistent_model\"}'
```

Git Bash:
```bash
curl -X POST http://localhost:5000/api/setup/model \
  -H "Content-Type: application/json" \
  -d '{"model":"nonexistent_model"}'
```

**기대 결과:**
```json
{
  "success": true,
  "message": "모델이 선택되었습니다."
}
```

**참고:**
- API는 성공 응답하지만 실제 채팅 시 에러 발생
- 다음 테스트: TC-4.1 (채팅)에서 에러 확인

**결과:** [ ] 성공 / [ ] 실패

---

### TC-15.6 존재하지 않는 리소스 조회

**테스트 항목:** 없는 활동 ID 조회

**사전 조건:** 로그인 완료

**테스트 방법:**

Windows PowerShell:
```powershell
curl.exe http://localhost:5000/api/activities/99999 `
  -b cookie.txt
```

Git Bash:
```bash
curl http://localhost:5000/api/activities/99999 \
  -b cookie.txt
```

**기대 결과:**
```json
{
  "detail": "Activity 99999 not found"
}
```

HTTP 상태 코드: 404

**결과:** [ ] 성공 / [ ] 실패

---

## 부록: 테스트 결과 기록표

### 전체 테스트 요약

| 섹션 | 총 테스트 | 성공 | 실패 | 건너뜀 |
|------|-----------|------|------|--------|
| 0. 테스트 환경 준비 | 9 | ___ | ___ | ___ |
| 1. 헬스 체크 | 1 | ___ | ___ | ___ |
| 2. 초기 설정 마법사 | 10 | ___ | ___ | ___ |
| 3. 인증 테스트 | 4 | ___ | ___ | ___ |
| 4. 채팅 테스트 | 3 | ___ | ___ | ___ |
| 5. 설정 관리 | 3 | ___ | ___ | ___ |
| 6. 플랫폼 연동 | 3 | ___ | ___ | ___ |
| 7. 활동 로그 | 3 | ___ | ___ | ___ |
| 8. 알림 | 3 | ___ | ___ | ___ |
| 9. 정보 수집 | 4 | ___ | ___ | ___ |
| 10. 슬래시 명령어 | 3 | ___ | ___ | ___ |
| 11. 긴급 정지 | 3 | ___ | ___ | ___ |
| 12. 백업/복구 | 2 | ___ | ___ | ___ |
| 13. WebSocket 실시간 상태 | 3 | ___ | ___ | ___ |
| 14. 프론트엔드 UI 테스트 | 8 | ___ | ___ | ___ |
| 15. 에러 시나리오 | 6 | ___ | ___ | ___ |
| **총계** | **68** | ___ | ___ | ___ |

---

### 테스트 환경 정보

| 항목 | 값 |
|------|-----|
| 테스트 일자 | _____________ |
| 테스터 이름 | _____________ |
| Python 버전 | _____________ |
| Node.js 버전 | _____________ |
| Ollama 버전 | _____________ |
| 사용한 LLM 모델 | _____________ |
| OS | _____________ |
| 백엔드 포트 | 5000 |
| 프론트엔드 포트 | 5173 |

---

### 주요 이슈 및 메모

| 테스트 ID | 이슈 내용 | 해결 방법 |
|-----------|-----------|-----------|
| TC-_____ | | |
| TC-_____ | | |
| TC-_____ | | |

---

### 테스트 완료 체크리스트

- [ ] 모든 필수 소프트웨어 설치 완료
- [ ] Ollama 서버 정상 작동
- [ ] 백엔드 서버 정상 시작
- [ ] 프론트엔드 서버 정상 시작
- [ ] 초기 설정 마법사 완료
- [ ] 로그인 성공
- [ ] 채팅 기능 작동
- [ ] WebSocket 연결 성공
- [ ] 설정 변경 및 저장 성공
- [ ] 긴급 정지 기능 작동
- [ ] 백업/복구 기능 작동
- [ ] 모든 UI 탭 정상 표시
- [ ] 에러 시나리오 검증 완료

---

## 테스트 완료

모든 테스트를 완료한 후:

1. 위의 테스트 결과 기록표 작성
2. 주요 이슈 및 메모 기록
3. 성공률 계산: (성공 / (총 테스트 - 건너뜀)) × 100%
4. 필요한 경우 실패한 테스트 재시도
5. 테스트 보고서 작성 및 공유

**성공률:** _______%

**전체 평가:**
- [ ] 우수: 95% 이상
- [ ] 양호: 80% ~ 94%
- [ ] 보통: 70% ~ 79%
- [ ] 미흡: 70% 미만

**추가 코멘트:**
_________________________________________________________________________
_________________________________________________________________________
_________________________________________________________________________
