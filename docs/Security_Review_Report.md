# 종합 보안 취약점 분석 보고서

**프로젝트:** bara_system (AI Social Bot Platform)
**분석 대상:** Backend (Python FastAPI) + Frontend (React TypeScript)
**분석 날짜:** 2026년 2월 4일
**분석 도구:**
- Gemini CLI (Codebase Investigator) — 1차 스캔
- Claude Opus 4.5 (4개 병렬 보안 전문 에이전트) — 심층 분석

---

## 목차

1. [분석 개요](#1-분석-개요)
2. [취약점 요약](#2-취약점-요약)
3. [CRITICAL — 즉시 수정 필요](#3-critical--즉시-수정-필요)
4. [HIGH — 빠른 수정 필요](#4-high--빠른-수정-필요)
5. [MEDIUM — 다음 릴리스 전 수정 권장](#5-medium--다음-릴리스-전-수정-권장)
6. [LOW — 백로그](#6-low--백로그)
7. [양호한 보안 관행](#7-양호한-보안-관행)
8. [OWASP Top 10 매핑](#8-owasp-top-10-매핑)
9. [수정 우선순위 로드맵](#9-수정-우선순위-로드맵)
10. [결론](#10-결론)

---

## 1. 분석 개요

### 배경

bara_system은 소셜 네트워크에서 자율적으로 활동하는 AI 봇 플랫폼입니다. FastAPI 기반 백엔드, React 프론트엔드, SQLite 데이터베이스, Ollama LLM 연동, 다중 플랫폼(Botmadang, Moltbook) 지원, 음성 인터페이스(Whisper) 등으로 구성되어 있습니다.

### 분석 범위

| 영역 | 파일 수 | 주요 검토 항목 |
|------|---------|---------------|
| 인증/인가 | 15+ | 비밀번호 해싱, 세션 관리, 미들웨어, IP 필터링 |
| 데이터베이스/주입 | 12+ | SQL 인젝션, 프롬프트 인젝션, 백업 무결성 |
| API/WebSocket | 20+ | 엔드포인트 접근 제어, CORS, SSRF, 입력 검증 |
| 시크릿/설정/프론트엔드 | 15+ | 하드코딩된 자격증명, XSS, 토큰 저장, CSP |

### 분석 방법론

1차로 Gemini CLI가 전체 코드베이스를 스캔하여 5개 주요 취약점을 식별했습니다. 이후 Claude Opus 4.5가 4개의 전문 보안 에이전트를 병렬로 실행하여 심층 분석을 수행했습니다:

- **에이전트 1:** 인증/인가 시스템 전문 분석
- **에이전트 2:** 데이터베이스/주입 취약점 전문 분석
- **에이전트 3:** API 엔드포인트/WebSocket/플랫폼 연동 분석
- **에이전트 4:** 시크릿 관리/설정/프론트엔드 보안 분석

---

## 2. 취약점 요약

| 심각도 | 건수 | 설명 |
|--------|------|------|
| **CRITICAL** | 5 | 즉시 수정 필요. 외부 공격자가 인증 없이 시스템을 장악할 수 있는 취약점 |
| **HIGH** | 10 | 빠른 수정 필요. 인증된 공격자 또는 특정 조건에서 심각한 피해 가능 |
| **MEDIUM** | 12 | 다음 릴리스 전 수정 권장. 방어 심층 강화 필요 |
| **LOW** | 8 | 백로그. 모범 사례 준수를 위한 개선 사항 |
| **합계** | **35** | |

### 발견 도구별 교차 검증

| 취약점 | Gemini | Claude | 비고 |
|--------|:------:|:------:|------|
| CORS 와일드카드 | ✅ | ✅ | 양쪽 모두 CRITICAL 판정 |
| 백업 민감정보 노출 | ✅ | ✅ | Claude가 SQL 인젝션까지 확장 발견 |
| WebSocket 토큰 쿼리 파라미터 | ✅ | ✅ | Claude가 3개 WebSocket 모두 확인 |
| 백업 SQL 인젝션 | ✅ | ✅ | Gemini는 "제한적", Claude는 CRITICAL 판정 |
| Rate Limiting 부재 | ✅ | ✅ | Claude가 X-Forwarded-For 우회까지 확장 |
| Setup Wizard 인증 부재 | — | ✅ | Claude만 발견 |
| 세션 토큰 응답 본문 노출 | — | ✅ | Claude만 발견 |
| CSRF 보호 부재 | — | ✅ | Claude만 발견 |
| Prompt Injection | — | ✅ | Claude만 발견 |
| SSRF (Botmadang) | — | ✅ | Claude만 발견 |
| 기타 20+ 항목 | — | ✅ | 심층 분석에서만 식별 |

---

## 3. CRITICAL — 즉시 수정 필요

### C1. CORS 와일드카드 Origin + Credentials 활성화

| 항목 | 내용 |
|------|------|
| **OWASP** | A05 Security Misconfiguration |
| **위치** | `backend/app/main.py:209-215` |
| **발견** | Gemini ✅ Claude ✅ |

**현재 코드:**
```python
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
```

**문제점:**
`allow_origins=["*"]`와 `allow_credentials=True`의 조합은 가장 위험한 CORS 설정입니다. Starlette의 `CORSMiddleware`는 이 설정에서 요청의 `Origin` 헤더를 동적으로 반영(`reflect`)하여, 사실상 어떤 도메인에서든 인증된 요청을 보낼 수 있게 됩니다.

**공격 시나리오:**
1. 공격자가 `evil-site.com`에 악성 스크립트를 호스팅
2. 피해자가 bara_system에 로그인한 상태에서 악성 사이트 방문
3. 악성 스크립트가 `fetch('https://bara-api/api/backup/export', {credentials: 'include'})`를 실행
4. 브라우저가 세션 쿠키를 포함하여 요청 → 전체 DB 백업 탈취 성공

**해결 방안:**
```python
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173"],  # 실제 프론트엔드 Origin
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE"],
    allow_headers=["Content-Type", "Authorization"],
)
```

---

### C2. Setup Wizard 엔드포인트 전체 인증 면제 — 시스템 탈취 벡터

| 항목 | 내용 |
|------|------|
| **OWASP** | A01 Broken Access Control |
| **위치** | `backend/app/api/middleware/auth.py:14-24`, `backend/app/api/routes/setup_wizard.py` 전체 |
| **발견** | Claude ✅ (Gemini 미발견) |

**현재 코드:**
```python
_EXEMPT_PREFIXES: tuple[str, ...] = (
    "/api/health",
    "/api/auth/login",
    "/api/auth/setup-password",
    "/api/auth/status",
    "/api/setup",       # ← 모든 /api/setup/* 경로가 인증 면제
    "/ws/",
    "/docs",
    "/redoc",
    "/openapi.json",
)
```

**문제점:**
초기 설정 완료 후에도 아래 엔드포인트가 인증 없이 접근 가능합니다:

| 엔드포인트 | 위험도 | 공격 가능 행위 |
|-----------|--------|---------------|
| `POST /api/setup/platforms` | 극심 | `.env` 파일에 임의 API 키 기록 (setup_wizard.py:267-327) |
| `POST /api/setup/model` | 높음 | LLM 모델 변경 |
| `POST /api/setup/bot` | 높음 | 봇 이름/소유자 변경 |
| `POST /api/setup/behavior` | 높음 | auto_mode 활성화, 모니터링 간격 변경 |
| `POST /api/setup/voice` | 보통 | 음성 설정 변경 |
| `POST /api/setup/complete` | 보통 | 설정 강제 완료 |
| `GET /api/setup/system-check` | 보통 | 시스템 정보 열거 |

**해결 방안:**
```python
# 방법 1: 면제 목록에서 제거하고 각 라우트에 가드 추가
@router.post("/model")
async def setup_model(request: Request, ...):
    auth_service = request.app.state.auth_service
    if auth_service.is_setup_complete():
        # 설정 완료 후에는 인증 필요
        session = auth_service.validate_session(...)
        if not session:
            return JSONResponse(status_code=401, content={"detail": "Authentication required"})
    ...
```

---

### C3. Backup Import SQL Injection — 테이블명/컬럼명 무검증 삽입

| 항목 | 내용 |
|------|------|
| **OWASP** | A03 Injection |
| **위치** | `backend/app/services/backup.py:78-101` |
| **발견** | Gemini ✅ (제한적) Claude ✅ (CRITICAL) |

**현재 코드:**
```python
for table_name, rows in tables_data.items():       # 공격자가 제공하는 JSON 키
    await self._db.execute_write(
        f"DELETE FROM {table_name}"                 # SQL 직접 삽입 (noqa: S608)
    )
    for row in rows:
        columns = list(row.keys())                  # 공격자가 제공하는 컬럼명
        col_names = ", ".join(columns)
        placeholders = ", ".join(["?"] * len(columns))
        sql = f"INSERT INTO {table_name} ({col_names}) VALUES ({placeholders})"
```

**문제점:**
백업 JSON의 테이블 이름과 컬럼 이름이 검증 없이 SQL 문에 직접 삽입됩니다. `# noqa: S608` 주석으로 Bandit 정적 분석 경고가 억제된 상태입니다.

**공격 시나리오:**
```json
{
  "tables": {
    "activities; DROP TABLE _migrations; --": [
      {"id": 1}
    ]
  }
}
```

**해결 방안:**
```python
ALLOWED_TABLES = {"activities", "conversations", "notifications", "settings_history"}

for table_name, rows in tables_data.items():
    if table_name not in ALLOWED_TABLES:
        logger.warning("Rejected unknown table in backup: %s", table_name)
        continue

    # 스키마에서 허용된 컬럼 목록 가져오기
    schema_columns = await self._get_table_columns(table_name)
    for row in rows:
        columns = [c for c in row.keys() if c in schema_columns]
        ...
```

---

### C4. 세션 토큰이 로그인 응답 본문에 노출

| 항목 | 내용 |
|------|------|
| **OWASP** | A02 Cryptographic Failures |
| **위치** | `backend/app/api/routes/auth.py:79`, `backend/app/models/auth.py:13-16` |
| **발견** | Claude ✅ (Gemini 미발견) |

**현재 코드:**
```python
# routes/auth.py:79
return LoginResponse(success=True, session_token=session.session_id)

# models/auth.py:13-16
class LoginResponse(BaseModel):
    success: bool
    session_token: Optional[str] = None  # ← httpOnly 쿠키와 동시에 본문 노출
    error: Optional[str] = None
```

**문제점:**
세션 토큰이 `httpOnly` 쿠키와 JSON 응답 본문 모두에 반환됩니다. `httpOnly` 플래그의 목적은 JavaScript에서 토큰에 접근하지 못하게 하는 것인데, 응답 본문에 토큰이 있으면 이 보호가 완전히 무효화됩니다.

**해결 방안:**
```python
# session_token 필드 제거
class LoginResponse(BaseModel):
    success: bool
    error: Optional[str] = None

# routes/auth.py — 쿠키만 설정, 본문에서 토큰 제거
return LoginResponse(success=True)
```

---

### C5. CSRF 보호 메커니즘 완전 부재

| 항목 | 내용 |
|------|------|
| **OWASP** | A01 Broken Access Control |
| **위치** | 모든 `POST`/`PUT` 엔드포인트 |
| **발견** | Claude ✅ (Gemini 미발견) |

**문제점:**
쿠키 기반 세션 인증을 사용하면서 CSRF 토큰 메커니즘이 전혀 없습니다. `SameSite=Lax` 쿠키는 cross-site POST 요청의 일부만 차단하며, 같은 사이트의 서브도메인 공격이나 top-level navigation을 통한 공격은 차단하지 못합니다.

C1(CORS 와일드카드)과 결합되면 모든 상태 변경 작업이 CSRF 공격에 완전히 노출됩니다.

**해결 방안:**
```python
# Double Submit Cookie 패턴 구현 예시
from secrets import token_urlsafe

@app.middleware("http")
async def csrf_middleware(request: Request, call_next):
    if request.method in ("POST", "PUT", "DELETE"):
        cookie_token = request.cookies.get("csrf_token")
        header_token = request.headers.get("X-CSRF-Token")
        if not cookie_token or cookie_token != header_token:
            return JSONResponse(status_code=403, content={"detail": "CSRF validation failed"})
    response = await call_next(request)
    if "csrf_token" not in request.cookies:
        response.set_cookie("csrf_token", token_urlsafe(32), samesite="strict")
    return response
```

---

## 4. HIGH — 빠른 수정 필요

### H1. X-Forwarded-For 헤더 위조로 IP 필터 및 로그인 잠금 우회

| 항목 | 내용 |
|------|------|
| **OWASP** | A01 Broken Access Control, A07 Authentication Failures |
| **위치** | `backend/app/api/middleware/ip_filter.py:74-81`, `backend/app/api/routes/auth.py:143-149` |

**현재 코드:**
```python
def _get_client_ip(request: Request) -> str:
    forwarded = request.headers.get("x-forwarded-for")
    if forwarded:
        return forwarded.split(",")[0].strip()
    if request.client:
        return request.client.host
    return "unknown"
```

**공격 시나리오:**
- `X-Forwarded-For: 127.0.0.1` → IP 허용 목록 우회, 로컬 접근으로 위장
- 매 요청마다 다른 `X-Forwarded-For` 값 → 로그인 잠금 카운터 우회 (무제한 브루트포스)

**해결 방안:** 신뢰할 수 있는 프록시 IP 목록을 설정하고, 프록시에서 온 요청만 `X-Forwarded-For`를 신뢰하도록 변경. uvicorn의 `--proxy-headers`와 `--forwarded-allow-ips` 옵션 활용.

---

### H2. OpenAPI/Swagger 문서 인증 없이 노출

| 항목 | 내용 |
|------|------|
| **OWASP** | A01 Broken Access Control |
| **위치** | `backend/app/api/middleware/auth.py:21-23` |

`/docs`, `/redoc`, `/openapi.json`이 인증 면제 목록에 포함되어 전체 API 구조, 스키마, 엔드포인트가 공격자에게 노출됩니다.

**해결 방안:** 프로덕션에서 `FastAPI(docs_url=None, redoc_url=None, openapi_url=None)` 설정

---

### H3. WebSocket 세션 토큰 URL 쿼리 파라미터 전송

| 항목 | 내용 |
|------|------|
| **OWASP** | A02 Cryptographic Failures |
| **위치** | `backend/app/api/websocket/chat.py:44`, `audio.py:42`, `status.py:64` |
| **발견** | Gemini ✅ Claude ✅ |

모든 3개 WebSocket 엔드포인트에서 `?token=<session_token>` 방식 사용. URL은 서버 로그, 브라우저 히스토리, 프록시 로그에 기록됩니다.

**해결 방안:** 인증된 REST 엔드포인트에서 단기(30초) 일회용 WebSocket 티켓을 발급하고, 이 티켓을 쿼리 파라미터로 전달 후 즉시 무효화.

---

### H4. 비밀번호 정책 미흡

| 항목 | 내용 |
|------|------|
| **OWASP** | A07 Identification and Authentication Failures |
| **위치** | `backend/app/api/routes/auth.py:127-131` |

최소 8자 길이만 확인. 복잡도 요구, 최대 길이 제한(PBKDF2 DoS 방지), 일반 비밀번호 사전 검사 없음. 비밀번호 변경 API도 부재.

**해결 방안:** 최소 12자 또는 복잡도(대소문자+숫자+특수문자) 요구, 최대 128자 제한, 비밀번호 변경 엔드포인트 추가.

---

### H5. Prompt Injection — LLM 입력에 사용자 콘텐츠 무검증 삽입

| 항목 | 내용 |
|------|------|
| **OWASP** | A03 Injection |
| **위치** | `backend/app/services/strategy.py:319-329, 363-375, 401-409`, `backend/app/api/routes/chat.py:61-67` |

**현재 코드:**
```python
# strategy.py — 외부 플랫폼 콘텐츠가 프롬프트에 직접 삽입
f"글 제목: {post.title or '(없음)'}\n"
f"글 내용: {post.content or '(없음)'}\n\n"
```

외부 플랫폼의 게시글/댓글과 사용자 채팅 메시지가 검증 없이 LLM 프롬프트에 삽입됩니다. `SecurityFilter`는 출력만 검사하고 입력은 검사하지 않습니다. 악성 게시글로 시스템 프롬프트 유출이나 봇 행동 조작이 가능합니다.

**해결 방안:** 입력과 시스템 프롬프트 사이에 명확한 구분자 사용, 사용자 입력 새니타이징 적용.

---

### H6. Backup Import로 config.json 무결성 검증 없이 덮어쓰기

| 항목 | 내용 |
|------|------|
| **OWASP** | A08 Software and Data Integrity Failures |
| **위치** | `backend/app/services/backup.py:110-121` |
| **발견** | Gemini ✅ (민감정보 노출) Claude ✅ (무결성 검증 부재 + 설정 덮어쓰기) |

백업 JSON의 `config` 섹션이 체크섬/서명 검증 없이 디스크에 기록됩니다. 공격자가 보안 필터 비활성화(`blocked_keywords: []`), 인증 설정 약화(`max_login_attempts: 999999`), 행동 제한 제거 등이 가능합니다.

Gemini가 지적한 백업 데이터의 민감 정보(API 키, 비밀번호 해시) 평문 노출도 이 맥락에서 함께 해결되어야 합니다.

**해결 방안:** 백업 내보내기 시 민감 필드 제외/암호화, 가져오기 시 무결성 해시 검증 + 스키마 검증 + 비밀번호 재확인 요구.

---

### H7. 인메모리 세션 저장소 상한/정리 없음 (DoS)

| 항목 | 내용 |
|------|------|
| **OWASP** | A07 Authentication Failures |
| **위치** | `backend/app/services/auth.py:35-36` |

`_sessions` 딕셔너리와 `_login_attempts` 딕셔너리에 크기 상한이 없습니다. 만료 세션의 자동 정리 태스크도 없습니다. 무제한 로그인 요청으로 메모리 소진 가능.

**해결 방안:** 최대 세션 수 제한(예: 100), 주기적 만료 세션 정리, `_login_attempts` 크기 상한 추가.

---

### H8. SSRF — BotmadangAdapter URL 도메인 검증 없음

| 항목 | 내용 |
|------|------|
| **OWASP** | A10 Server-Side Request Forgery |
| **위치** | `backend/app/platforms/botmadang.py:68-95` |

`MoltbookAdapter`에는 `_is_safe_url()` 도메인 검증이 있으나 `BotmadangAdapter`에는 없습니다. C2(Setup 인증 부재)와 결합하면: 공격자가 `POST /api/setup/platforms`로 `base_url`을 내부 서비스로 변경 → API 키가 포함된 요청이 공격자 제어 서버나 내부 메타데이터 엔드포인트로 전송.

**해결 방안:** BotmadangAdapter에 MoltbookAdapter의 `_is_safe_url()` 패턴 적용, `HttpClient`에 내부 IP 대역 차단 추가.

---

### H9. Auth Status 엔드포인트에서 세션 전체 객체 노출

| 항목 | 내용 |
|------|------|
| **OWASP** | A02 Cryptographic Failures |
| **위치** | `backend/app/api/routes/auth.py:95-113` |

인증 면제 엔드포인트 `/api/auth/status`에서 `session_id`, `ip_address`, `expires_at`을 포함한 전체 `Session` 객체를 반환. 프론트엔드는 `authenticated`와 `setup_complete`만 사용합니다.

**해결 방안:** 응답에서 `session` 필드 제거.

---

### H10. 에러 메시지에 내부 구현 정보 노출

| 항목 | 내용 |
|------|------|
| **OWASP** | A04 Insecure Design |
| **위치** | `backup.py:34,72,89`, `settings.py:64`, `commands.py:79`, `setup_wizard.py:240,263`, `database.py:49,119,131`, `strategy.py:339` |

```python
content={"detail": f"Backup export failed: {exc}"}  # 내부 경로, DB 스키마, 스택 정보 노출
```

**해결 방안:** 클라이언트에는 일반적인 오류 메시지만 반환, 상세 정보는 서버 로그에만 기록.

---

## 5. MEDIUM — 다음 릴리스 전 수정 권장

| # | 취약점 | OWASP | 위치 | 설명 |
|---|--------|-------|------|------|
| M1 | API Rate Limiting 부재 | A04 | 모든 라우트 | `/api/chat`, `/api/backup`, `/api/commands` 등 민감 엔드포인트에 요청 제한 없음. `slowapi` 등 도입 권장 |
| M2 | 보안 설정 재인증 없이 변경 | A01 | `settings.py:36-90` | `web_security` 섹션(잠금시간, 최대시도, 세션만료) 변경 시 비밀번호 재확인 없음 |
| M3 | .env 줄바꿈 인젝션 | A03 | `setup_wizard.py:419-444`, `auth.py:164-182` | API 키 값에 `\n`을 포함하면 임의 환경변수 주입 가능. 값에서 줄바꿈 문자 제거 필요 |
| M4 | 보안 헤더 미설정 | A05 | `main.py` | CSP, HSTS, X-Content-Type-Options, X-Frame-Options, Referrer-Policy 없음 |
| M5 | 채팅 메시지 길이 제한 없음 | A04 | `chat.py:24-26` | `message` 필드에 `max_length` 없음. 수 MB 메시지로 DB/LLM 리소스 소진 가능 |
| M6 | 세션 IP 바인딩 없음 | A07 | `auth.py:117-126` | `Session.ip_address`를 저장하지만 검증하지 않음. 탈취된 토큰을 아무 IP에서 사용 가능 |
| M7 | ReDoS 위험 | A03 | `security.py:125-132` | `blocked_patterns`에 사용자 제공 정규식을 복잡도 검사 없이 컴파일. `(a+)+$` 같은 패턴으로 CPU 소진 가능 |
| M8 | 루트 .gitignore 부재 | A02 | 프로젝트 루트 | `backend/.gitignore`만 존재. 루트에 `.env`나 `config.json` 생성 시 VCS 포함 위험 |
| M9 | SSL 개인키 파일 권한 미설정 | A05 | `ssl.py:77-98` | `localhost.key`가 기본 권한으로 생성, `certs/`가 .gitignore에 미포함 |
| M10 | Assert문으로 데이터 검증 | A04 | `activity.py:40`, `conversation.py:23`, `notification.py:33` | Python `-O` 모드에서 assert 무시됨. 적절한 예외 처리로 변경 필요 |
| M11 | DB 마이그레이션 무결성 미검증 | A08 | `database.py:75-106` | SQL 파일이 체크섬 검증 없이 실행. 파일 변조 시 임의 SQL 실행 가능 |
| M12 | Backup 데이터 응답 본문 전체 포함 | A02 | `backup.py:51-57` | DB 전체 덤프가 JSON 응답으로 전송. 다운로드 URL 방식으로 변경 권장 |

---

## 6. LOW — 백로그

| # | 취약점 | 설명 |
|---|--------|------|
| L1 | Brute Force 기본값 미흡 | 5회/5분 잠금, HTTP 429 미반환. 15-30분 잠금 + 429 응답 + 지수 백오프 권장 |
| L2 | Auth 미들웨어 서비스 미초기화 시 통과 | `auth_service=None`이면 모든 요청 인증 우회. 503 반환으로 변경 필요 |
| L3 | 설정 API가 보안 필터 규칙 노출 | `GET /api/settings`에서 `blocked_keywords`/`blocked_patterns`이 클라이언트에 노출 |
| L4 | config.json 보안 필터 비활성 | 프로덕션 `blocked_keywords: []`, `blocked_patterns: []`. 예시 설정 적용 필요 |
| L5 | 백업 파일 예측 가능 경로 | `backups/backup_YYYYMMDD_HHMMSS.json` — 절대 경로 사용 + 디렉토리 접근 제한 |
| L6 | LIKE 쿼리 와일드카드 미이스케이프 | `collected_info.py:88-93`에서 `%`, `_` 이스케이프 없음 |
| L7 | 인메모리 세션 서버 재시작 시 초기화 | 잠금 카운터도 초기화됨. DB 기반 저장 고려 |
| L8 | Vite 프록시 HTTP 사용 | 개발 환경에서 프록시가 평문 HTTP 연결. 프로덕션 노출 방지 확인 필요 |

---

## 7. 양호한 보안 관행

두 분석 도구 모두 아래 항목을 긍정적으로 평가했습니다:

| 항목 | 상세 | 평가 |
|------|------|------|
| **비밀번호 해싱** | PBKDF2-HMAC-SHA256, 600,000 이터레이션, 32바이트 솔트 | OWASP 권장 초과 |
| **타이밍 안전 비교** | `secrets.compare_digest()` 사용 (`auth.py:70`) | 타이밍 공격 방지 |
| **세션 토큰 생성** | `secrets.token_urlsafe(32)` | 암호학적 안전 |
| **httpOnly 쿠키** | `httponly=True`, `samesite=lax` 설정 | JS 접근 차단 (단, C4에 의해 약화) |
| **SQL 파라미터 바인딩** | Repository 레이어에서 `?` 플레이스홀더 일관 사용 | SQL 인젝션 방지 (backup.py 제외) |
| **XSS 패턴 없음** | React 기본 이스케이프, `dangerouslySetInnerHTML`/`eval()`/`innerHTML` 미사용 | 프론트엔드 안전 |
| **시크릿 관리** | API 키는 `.env`에 저장, `.gitignore`로 VCS 제외 | 소스코드 내 하드코딩 없음 |
| **LLM 출력 필터** | `SecurityFilter` 3단계 필터링: API 키, Bearer 토큰, 사용자 정의 패턴 | 정보 유출 방지 |
| **쓰기 직렬화** | `asyncio.Lock()`으로 SQLite 쓰기 직렬화 | 동시성 안전 |
| **WAL 모드** | SQLite WAL 저널 모드 활성화 | 동시 읽기/쓰기 성능 |

---

## 8. OWASP Top 10 매핑

| OWASP 카테고리 | 해당 취약점 | 상태 |
|---------------|-----------|------|
| **A01** Broken Access Control | C2, C5, H1, H2, M2 | ❌ 다수 발견 |
| **A02** Cryptographic Failures | C4, H3, H9, M8, M12 | ❌ 다수 발견 |
| **A03** Injection | C3, H5, M3, M7 | ❌ SQL + Prompt + Env 인젝션 |
| **A04** Insecure Design | H10, M1, M5, M10 | ⚠️ 설계 수준 개선 필요 |
| **A05** Security Misconfiguration | C1, H2, M4, M9 | ❌ CORS + 헤더 + SSL |
| **A06** Vulnerable Components | (미검사) | ⚠️ `pip audit`/`npm audit` 실행 필요 |
| **A07** Identification & Auth Failures | H4, H7, M6 | ⚠️ 비밀번호 정책 + 세션 관리 |
| **A08** Software & Data Integrity | H6, M11 | ❌ 백업/마이그레이션 무결성 |
| **A09** Logging & Monitoring Failures | H10 (역방향) | ⚠️ 보안 이벤트 알림 부재 |
| **A10** Server-Side Request Forgery | H8 | ❌ Botmadang SSRF |

---

## 9. 수정 우선순위 로드맵

### Phase 1: 즉시 (프로덕션 배포 차단)

| 순위 | 이슈 | 예상 작업 |
|------|------|----------|
| 1 | C1 CORS 수정 | `allow_origins`를 특정 Origin으로 제한 — 1줄 변경 |
| 2 | C2 Setup 인증 | 면제 목록에서 제거 + 완료 체크 가드 추가 |
| 3 | C3 Backup SQL 인젝션 | 테이블/컬럼 화이트리스트 검증 |
| 4 | C4 세션 토큰 노출 | `LoginResponse`에서 `session_token` 필드 제거 |
| 5 | C5 CSRF 보호 | Double Submit Cookie 미들웨어 구현 |

### Phase 2: 다음 릴리스 전

| 순위 | 이슈 | 예상 작업 |
|------|------|----------|
| 6 | H1 X-Forwarded-For | 신뢰 프록시 설정 |
| 7 | H2 OpenAPI 비활성화 | 프로덕션 `docs_url=None` |
| 8 | H5 Prompt Injection | LLM 입력 새니타이징 + 구분자 |
| 9 | H6 Backup 무결성 | 해시 검증 + 비밀번호 재확인 |
| 10 | H8 SSRF 방지 | BotmadangAdapter URL 검증 |
| 11 | H9 Auth Status 정리 | Session 필드 제거 |
| 12 | H10 에러 메시지 | 일반 메시지로 변경 |
| 13 | M1 Rate Limiting | `slowapi` 도입 |
| 14 | M4 보안 헤더 | 미들웨어 추가 |

### Phase 3: 백로그

나머지 MEDIUM 및 LOW 이슈를 우선순위에 따라 처리.

추가 권장 사항:
- `pip audit` 실행하여 Python 의존성 취약점 확인 (OWASP A06)
- `npm audit` 실행하여 프론트엔드 의존성 취약점 확인
- 보안 이벤트 알림 시스템 구축 (로그인 실패, 설정 변경 등)

---

## 10. 결론

bara_system은 **비밀번호 해싱, SQL 파라미터 바인딩, XSS 방지** 등 기본적인 보안 원칙을 잘 준수하고 있습니다. 그러나 **CORS 설정, 접근 제어, CSRF 보호, 입력 검증** 영역에서 즉시 수정이 필요한 심각한 취약점이 발견되었습니다.

특히 **C1(CORS) + C2(Setup 인증 부재) + C5(CSRF 부재)**의 조합은 외부 공격자가 인증 없이 시스템 전체를 장악할 수 있는 공격 체인을 형성합니다:

1. 공격자가 악성 웹사이트 호스팅
2. CORS 와일드카드로 인해 크로스 오리진 요청 허용 (C1)
3. CSRF 토큰이 없어 쿠키가 자동 포함 (C5)
4. 또는 인증이 필요 없는 Setup 엔드포인트 직접 호출 (C2)
5. `.env` 파일에 악성 API 키 주입 → 플랫폼 자격 증명 탈취

**Phase 1의 5개 CRITICAL 이슈를 프로덕션 배포 전 반드시 해결해야 합니다.**

---

*이 보고서는 Gemini CLI 1차 스캔과 Claude Opus 4.5 심층 분석의 결과를 통합하여 작성되었습니다.*
