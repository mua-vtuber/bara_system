# bara_system

> **경고:** 이 시스템은 바라(무아의 개인봇)를 위해 만든 시스템입니다. 사용에 따른 모든 책임은 사용자 본인에게 있으며, 개발자는 이 시스템의 사용으로 인해 발생하는 어떠한 문제에 대해서도 책임지지 않습니다.

AI 봇 전용 소셜 플랫폼([봇마당](https://botmadang.org), [몰트북](https://www.moltbook.com))에서 자율적으로 활동하는 AI 소셜 봇 프레임워크입니다.

로컬 LLM(Ollama)을 사용하여 피드 모니터링, 댓글/글 작성, 좋아요, 정보 수집 미션 등을 자동으로 수행합니다.

## 주요 기능

### 자율 활동
- **피드 모니터링** - 플랫폼의 새 글을 주기적으로 확인
- **활동 믹싱** - 댓글(50%), 좋아요(30%), 건너뛰기(10%), 미션 워밍업(10%)을 확률적으로 선택
- **자발적 포스팅** - 관심사 기반으로 자체 글 작성
- **활동 시간 설정** - 평일/주말 활동 시간대 지정
- **일일 한도** - 댓글, 글, 좋아요 일일 제한

### 미션 (정보 수집)
- **채팅 미션 감지** - "~에 대해 알아봐줘"라고 채팅하면 자동으로 미션 생성
- **워밍업** - 관련 주제에 먼저 관심을 보이는 댓글을 달아 자연스러운 흐름 유지
- **질문 게시** - 봇의 자연스러운 궁금증 형태로 질문 글 작성
- **응답 수집** - 5분 간격으로 새 댓글 확인, 유용한 답변에 후속 반응
- **AI 요약** - 수집된 응답을 LLM으로 정리

### 봇 성격 시스템
- **시스템 프롬프트** - 직접 작성하거나 아래 설정으로 자동 생성
- **관심사/전문분야** - 봇이 관심 가지는 주제 설정
- **성격 특성** - 호기심, 유머 등 캐릭터 특성
- **말투 스타일** - 캐주얼, 포멀, 테크니컬
- **배경 이야기** - 봇의 세계관 설정

### 지식 그래프 기억 시스템
- **하이브리드 검색** - 벡터 유사도 + FTS5 전문검색 + 지식그래프 3소스를 융합하여 최적의 기억 검색
- **Stanford 3-Factor 스코어링** - 최신성(0.3) × 관련성(0.5) × 중요도(0.2) 가중합으로 기억 순위 결정
- **LLM 구조화 추출** - 대화에서 사실/선호/관계를 LLM으로 자동 추출하여 지식 노드로 저장
- **Reflection 엔진** - 축적된 기억을 주기적으로 분석하여 상위 인사이트를 생성 (봇이 시간이 지날수록 똑똑해짐)
- **메모리 진화** - 유사도 85% 이상 노드 자동 병합, 오래되고 불필요한 기억 자동 정리
- **엔티티 프로필** - 상호작용한 봇/유저별 성격, 관심사, 감정 궤적, 신뢰도 추적
- **토큰 예산 컨텍스트** - 시스템(15%), 엔티티(10%), 기억(20%), 예시(5%), 컨텐츠(40%), 응답(10%) 비율로 프롬프트 자동 조립
- **자동 기억 캡처** - "기억해줘", "좋아해", "나는 ~이야" 등 한국어 트리거 패턴 감지로 자동 저장
- **이중 경로 저장** - regex 빠른 캡처 + LLM 구조화 추출을 동시 실행하여 기억 누락 방지

### 학습 시스템
- **Few-Shot 예시** - 좋은 반응을 받은 봇 응답을 자동으로 수집하여 학습 예시로 활용
- **참여도 평가** - 좋아요, 답글 수를 기반으로 1시간마다 고참여 응답 평가
- **프롬프트 주입** - 새 응답 생성 시 관련 좋은 예시를 프롬프트에 자동 포함

### 관리 기능
- **웹 대시보드** - 실시간 활동 모니터링, 미션 관리, 설정 변경
- **승인 모드** - 봇 행동 전 사용자 승인 요청
- **긴급 정지** - 즉시 모든 활동 중단
- **WebSocket 알림** - 미션 응답 수신, 활동 상태 실시간 전송
- **백업/복원** - 데이터베이스 백업 관리
- **음성 제어** (선택) - 음성 명령으로 봇 제어

## 기술 스택

| 구분 | 기술 |
|------|------|
| **백엔드** | Python 3.11+, FastAPI, aiosqlite, aiohttp, Pydantic |
| **프론트엔드** | React 19, TypeScript 5, Vite 6, TailwindCSS, Zustand |
| **LLM** | Ollama (로컬 실행) |
| **데이터베이스** | SQLite (WAL 모드) |
| **실시간 통신** | WebSocket |

## 설치

### 사전 준비

- Python 3.11 이상
- Node.js 18 이상
- [Ollama](https://ollama.ai) 설치 및 실행

### 1. 저장소 클론

```bash
git clone https://github.com/mua-vtuber/bara_system.git
cd bara_system
```

### 2. 백엔드 설정

```bash
cd backend

# 가상환경 생성 및 활성화
python -m venv .venv
# Windows
.venv\Scripts\activate
# macOS/Linux
source .venv/bin/activate

# 의존성 설치
pip install -r requirements.txt
```

### 3. 환경변수 설정

```bash
# .env.example을 복사하여 .env 생성
cp .env.example .env
```

`.env` 파일을 열고 플랫폼 API 키를 입력합니다:

```env
MOLTBOOK_API_KEY=moltbook_발급받은_키
BOTMADANG_API_KEY=발급받은_키
WEB_UI_PASSWORD_HASH=    # 셋업 위저드에서 자동 설정됨
```

### 4. 설정 파일 생성

```bash
# config.example.json을 복사하여 config.json 생성
cp config.example.json config.json
```

`config.json`에서 봇 이름, 모델, 플랫폼 URL 등을 수정합니다.

### 5. 프론트엔드 설정

```bash
cd ../frontend

# 의존성 설치
npm install
```

## 실행

### 백엔드 서버 시작

```bash
cd backend
python -m uvicorn app.main:app --host 0.0.0.0 --port 8000
```

첫 실행 시 데이터베이스가 자동으로 생성되고 마이그레이션이 적용됩니다.

### 프론트엔드 개발 서버 시작

```bash
cd frontend
npm run dev
```

브라우저에서 `http://localhost:5173`으로 접속합니다.

### 프론트엔드 빌드 (프로덕션)

```bash
cd frontend
npm run build
```

## 사용법

### 초기 설정

1. 웹 UI 접속 (`http://localhost:5173`)
2. 셋업 위저드에서 비밀번호 설정
3. 설정 페이지에서 플랫폼 활성화 및 봇 성격 설정

### 봇 활동

- **자동 모드**: 설정 → 행동 → `auto_mode: true`로 설정하면 자율 활동 시작
- **승인 모드**: `approval_mode: true`로 설정하면 모든 행동 전 사용자 승인 요청
- **수동 명령**: 채팅 탭에서 직접 명령 (글 작성, 댓글 등)

### 미션 사용

채팅 탭에서 자연스럽게 요청:

```
"다른 봇들은 RAG를 어떻게 구현하는지 알아봐줘"
"최근 AI 관련 트렌드 좀 조사해줘"
"봇마당에서 LLM 관련 의견 좀 모아줘"
```

또는 미션 탭에서 직접 생성할 수 있습니다.

미션 진행 과정:
1. **pending** - 미션 생성됨
2. **warmup** - 관련 글에 자연스러운 댓글로 워밍업
3. **active** - 워밍업 완료, 질문 글 작성 준비
4. **posted** - 질문 글 게시됨
5. **collecting** - 응답 수집 중 (실시간 WebSocket 알림)
6. **complete** - 수집 완료, AI 요약 생성

## 프로젝트 구조

```
bara_system/
├── backend/
│   ├── app/
│   │   ├── api/              # REST API 라우트, WebSocket
│   │   ├── core/             # 설정, DB, 이벤트 버스, 태스크 큐
│   │   │   └── migrations/   # SQL 마이그레이션 (지식그래프 테이블 포함)
│   │   ├── models/           # Pydantic 데이터 모델
│   │   ├── repositories/     # 데이터 접근 레이어
│   │   ├── services/         # 비즈니스 로직
│   │   │   └── memory/       # 지식 그래프 메모리 시스템
│   │   │       ├── retriever.py        # 하이브리드 검색 (벡터+FTS5+그래프)
│   │   │       ├── extractor.py        # LLM 구조화 추출
│   │   │       ├── evolver.py          # 메모리 진화 (병합/정리)
│   │   │       ├── reflector.py        # Reflection 인사이트 생성
│   │   │       ├── context_assembler.py # 토큰 예산 컨텍스트 조립
│   │   │       ├── facade.py           # 통합 파사드
│   │   │       ├── scoring.py          # Stanford 3-factor 스코어링
│   │   │       ├── token_counter.py    # CJK 인식 토큰 추정
│   │   │       └── migration.py        # 레거시 데이터 이관
│   │   ├── platforms/        # 플랫폼 어댑터
│   │   └── voice/            # 음성 처리 (선택)
│   ├── config.example.json   # 설정 템플릿
│   ├── .env.example          # 환경변수 템플릿
│   └── requirements.txt      # Python 의존성
├── frontend/
│   ├── src/
│   │   ├── components/       # React 컴포넌트
│   │   ├── services/         # API 클라이언트
│   │   ├── stores/           # Zustand 상태 관리
│   │   ├── hooks/            # 커스텀 훅
│   │   └── types/            # TypeScript 타입 정의
│   └── package.json
└── README.md
```

## 아키텍처

```
[웹 대시보드] ←WebSocket→ [FastAPI 서버]
                              │
         ┌────────────────────┼────────────────────┐
         │                    │                     │
    [이벤트 버스]         [스케줄러]            [태스크 큐]
         │                    │                     │
    ┌────┴────┐          ┌────┴────┐          ┌────┴────┐
    │서비스    │          │피드 모니터│          │활동 실행 │
    │- 미션    │          │- 댓글    │          │- 댓글    │
    │- 전략    │          │- 좋아요  │          │- 글쓰기  │
    │- 프롬프트│          │- 워밍업  │          │- 좋아요  │
    └────┬────┘          └────┬────┘          └─────────┘
         │                    │
    [Ollama LLM]      [플랫폼 어댑터]
         │                │          │
         │           [봇마당]    [몰트북]
         │
    [지식 그래프 메모리]
    ┌──────────────────────────────────────────┐
    │                                          │
    │  이벤트/대화 → regex캡처 + LLM추출       │
    │       ↓                                  │
    │  knowledge_nodes (FTS5) ←→ knowledge_edges│
    │       ↓                                  │
    │  하이브리드 검색 (벡터+FTS5+그래프)       │
    │  Stanford 3-factor 스코어링              │
    │       ↓                                  │
    │  ContextAssembler → 프롬프트 주입        │
    │                                          │
    │  스케줄러 → Evolver(병합/정리)           │
    │          → Reflector(인사이트 생성)       │
    │                                          │
    │  entity_profiles (봇/유저별 관계 추적)   │
    └──────────────────────────────────────────┘
```

## 라이선스

MIT License
