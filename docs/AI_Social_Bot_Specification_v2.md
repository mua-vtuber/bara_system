# AI Social Bot - 프로젝트 기획서 v2

**버전:** 2.0
**작성일:** 2026-02-03
**작성자:** 무아 & Claude

---

## 목차

1. [프로젝트 개요](#1-프로젝트-개요)
2. [기술 스택](#2-기술-스택)
3. [시스템 구조](#3-시스템-구조)
4. [플랫폼 API 정합성](#4-플랫폼-api-정합성)
5. [봇 행동 전략](#5-봇-행동-전략)
6. [주요 기능](#6-주요-기능)
7. [음성 입력 설계](#7-음성-입력-설계)
8. [UI 설계](#8-ui-설계)
9. [데이터베이스 스키마](#9-데이터베이스-스키마)
10. [에러 핸들링 전략](#10-에러-핸들링-전략)
11. [보안](#11-보안)
12. [24/7 안정 운영 설계](#12-247-안정-운영-설계)
13. [설정 파일 구조](#13-설정-파일-구조)
14. [초기 설정 마법사](#14-초기-설정-마법사)
15. [구현 우선순위](#15-구현-우선순위)
16. [성공 지표](#16-성공-지표)
17. [범용화 설계 원칙](#17-범용화-설계-원칙)
18. [오픈소스 계획](#18-오픈소스-계획)
19. [참고 자료](#19-참고-자료)
20. [Claude Code 지시사항](#20-claude-code-지시사항)

---

## 1. 프로젝트 개요

### 목적
- Moltbook/봇마당 등 AI 에이전트 SNS에서 자동으로 기술 정보 수집
- 적당한 소셜 활동으로 "날먹 유저" 방지
- 사용자의 수동 요청 시 도움 요청 글 자동 작성
- **AI 에이전트 SNS용 봇 프레임워크 제공**

### 핵심 가치
1. **정보 수집**: 다른 AI들로부터 기술 정보 무료로 획득
2. **자동화**: 24/7 자동 활동으로 커뮤니티 참여 유지
3. **범용성**: 누구나 자신만의 봇 캐릭터로 커스터마이징 가능

---

## 2. 기술 스택

### Frontend
- **Framework**: React + Vite
- **UI Library**: Tailwind CSS, shadcn/ui 등 선택
- **통신**: WebSocket (실시간 업데이트)

### Backend
- **Framework**: FastAPI (Python)
- **Wake Word Engine**: openWakeWord 또는 Porcupine (음성 1단계 감지)
- **음성 인식(STT)**: OpenAI Whisper (2단계, 호출어 감지 시에만 가동)
- **LLM**: Ollama (로컬 모델)
- **데이터베이스**: SQLite (WAL 모드 기본)
- **API 연동**: Moltbook, 봇마당(Botmadang)

### 하드웨어 요구사항

| 등급 | GPU VRAM | 설명 |
|------|----------|------|
| **최소** | 8GB VRAM | 텍스트 기능만 사용 가능. 음성 기능 제한적 (LLM + Whisper 동시 사용 불가) |
| **권장** | 12GB+ VRAM | 음성 기능 사용 가능. 7B LLM + Whisper small 동시 로딩 가능 |
| **최적** | 24GB+ VRAM | 모든 기능 동시 사용. 13B+ LLM + Whisper medium/large 동시 가동 |

### 시스템 구성 예시
- **보조 PC (서버)**: GPU 탑재, Ollama + FastAPI 실행
- **작업 PC (클라이언트)**: 웹 브라우저만 있으면 됨
- **네트워크**: 로컬 네트워크 또는 인터넷 연결

---

## 3. 시스템 구조

### 아키텍처 다이어그램

```
작업 PC (웹 브라우저)
    ├─ HTTP/REST (API 호출)
    ├─ WebSocket (실시간 상태, 알림)
    └─ WebSocket (오디오 스트리밍, MediaStream API)
        ↓
보조 PC (FastAPI Server :5000)
    ├─ Wake Word Engine (openWakeWord/Porcupine, CPU만 사용)
    ├─ Whisper (호출어 감지 시에만 GPU 사용)
    ├─ Ollama (LLM)
    ├─ SQLite (메모리/로그)
    ├─ Rate Limiter (플랫폼별 독립 인스턴스)
    ├─ Notification Poller (알림 폴링)
    ├─ Behavior Engine (행동 전략 엔진)
    └─ Platform APIs
        ├─ Moltbook API (https://www.moltbook.com/api/v1/)
        └─ Botmadang API (https://botmadang.org/api/v1/)
```

### 오디오 스트리밍 경로

```
작업 PC 브라우저
    → MediaStream API로 마이크 접근
    → WebSocket으로 오디오 청크 전송
    → 보조 PC에서 수신
    → Stage 1: Wake Word Engine (CPU) - 항상 활성
    → 감지 시 Stage 2: Whisper (GPU) - 명령 인식 후 언로드
```

### 파일 구조

```
ai-social-bot/
├── README.md
├── SETUP.md
├── .env.example                    # API Key 등 시크릿 예시
├── config.example.json             # 설정 파일 예시 (git 커밋 대상)
├── .gitignore                      # .env, config.json 포함
├── personalities/
│   ├── bara.Modelfile              # 기본 제공 예시
│   ├── helper.Modelfile            # 다른 예시
│   └── custom.Modelfile.template
├── frontend/
│   ├── package.json
│   ├── vite.config.js
│   └── src/
│       ├── App.jsx
│       ├── components/
│       │   ├── Chat.jsx
│       │   ├── ActivityLog.jsx
│       │   ├── InfoCollection.jsx
│       │   └── Settings.jsx
│       ├── config.js
│       └── utils/
├── backend/
│   ├── requirements.txt
│   ├── main.py
│   ├── config.py
│   ├── bot/
│   │   ├── core.py
│   │   ├── voice.py
│   │   ├── memory.py
│   │   ├── notifications.py        # 알림 폴링 및 대응
│   │   ├── strategy.py             # 행동 전략 엔진
│   │   ├── rate_limiter.py         # 플랫폼별 Rate Limiter
│   │   └── platforms/
│   │       ├── base.py             # 플랫폼 어댑터 인터페이스
│   │       ├── moltbook.py
│   │       └── botmadang.py
│   └── filters.py
├── logs/
│   ├── activity.log
│   ├── filtered.log
│   ├── errors.log
│   └── api.log
└── docs/
    ├── CREATE_BOT.md
    ├── CUSTOMIZATION.md
    └── API.md
```

---

## 4. 플랫폼 API 정합성

### 올바른 Base URL

| 플랫폼 | 올바른 Base URL | 주의사항 |
|--------|----------------|----------|
| **Moltbook** | `https://www.moltbook.com/api/v1/` | `www` 필수. 누락 시 리다이렉트 과정에서 Authorization 헤더 탈락 |
| **봇마당** | `https://botmadang.org/api/v1/` | `/v1/` 경로 필수 |

### 봇마당 인증 흐름

봇마당은 API Key를 직접 입력하는 방식이 아니라, 별도의 등록/인증 프로세스를 거칩니다.

```
1. POST /api/v1/agents/register (인증 없이 요청)
   ├─ 요청: { "name": "봇이름", "description": "한국어 자기소개" }
   └─ 응답: { "claim_url": "https://botmadang.org/claim/madang-XXXX",
              "verification_code": "madang-XXXX" }

2. 사용자(사람)에게 claim_url 표시
   └─ 사용자가 브라우저에서 claim_url 열기

3. 사용자가 X/Twitter에 verification_code를 트윗

4. 봇이 인증 완료 여부 폴링 (주기적 확인)

5. 인증 완료 → API Key 수신 → .env 파일에 저장
```

### 플랫폼별 Rate Limit

```
봇마당:
  - 글 작성: 3분당 1개 (쿨다운 기반)
  - 댓글 작성: 10초당 1개 (쿨다운 기반)
  - API 요청: 100회/분

Moltbook:
  - 글 작성: 30분당 1개 (쿨다운 기반)
  - 댓글 작성: 20초당 1개 (쿨다운 기반) + 일일 50개 상한
  - API 요청: 100회/분
```

### 플랫폼별 API 기능 목록

**봇마당:**

| 기능 | 엔드포인트 | 인증 |
|------|-----------|------|
| 에이전트 등록 | POST /agents/register | 불필요 |
| 내 정보 조회 | GET /agents/me | 필요 |
| 글 목록 | GET /posts | 불필요 |
| 글 작성 | POST /posts | 필요 |
| 댓글 작성 | POST /posts/:id/comments | 필요 |
| 추천 | POST /posts/:id/upvote | 필요 |
| 비추천 | POST /posts/:id/downvote | 필요 |
| 마당 목록 조회 | GET /submadangs | 필요 |
| 새 마당 생성 | POST /submadangs | 필요 |
| 알림 조회 | GET /notifications | 필요 |
| 알림 읽음 처리 | POST /notifications/read | 필요 |

기본 마당(submadang) 목록:
- `general` (자유게시판)
- `tech` (기술토론)
- `daily` (일상)
- `questions` (질문답변)
- `showcase` (자랑하기)

규칙:
- 한국어 필수
- 스팸 금지
- API 키 비공개

**Moltbook:**

| 기능 | 설명 |
|------|------|
| 글 작성/조회 | posts CRUD |
| 댓글 (Nested) | 대댓글 지원 |
| 투표 | upvote/downvote |
| Submolts | 커뮤니티 분류 (봇마당의 submadang에 대응) |
| Follow/Unfollow | 에이전트 팔로우 |
| 시맨틱 검색 | 의미 기반 검색 (키워드 매칭보다 강력) |
| 피드 정렬 | hot, new, top, rising |

인증:
- API Key 형식: `moltbook_` 접두사
- Key 전송 도메인: `www.moltbook.com` 이외 도메인으로 전송 차단 필수

---

## 5. 봇 행동 전략

### 5.1 피드 모니터링 전략

매 N분(기본 30분)마다 각 플랫폼의 새 글 목록을 조회합니다.

**Moltbook:**
- 시맨틱 검색 API를 활용하여 관심 키워드 검색 (Unity, Spine, C# 등)
- 피드 정렬: `hot`과 `new`를 혼합하여 조회
- 팔로우한 에이전트의 글 우선 처리

**봇마당:**
- 최신 글 목록에서 관심 키워드 필터링
- 정렬: 최신순
- 마당(submadang)별 필터링: `tech`, `questions` 우선

### 5.2 댓글 의사결정 로직

```
새 글 발견
  |
  +--> 관심 키워드 포함?
  |      |
  |      +--> YES: "관심 큐"에 추가
  |      |
  |      +--> NO: 건너뜀
  |
  +--> 관심 큐에서 글 선택
  |
  +--> 이미 댓글 달았는지 확인 (DB 조회, platform_post_id 기준)
  |      |
  |      +--> 이미 달음: 건너뜀
  |
  +--> 원글 전체를 LLM에 전달
  |
  +--> LLM이 댓글 생성
  |
  +--> 품질 체크
  |      ├── 최소 길이 확인 (20자 이상)
  |      ├── 원글과의 관련성 확인
  |      └── 봇마당인 경우 한국어 비율 검사 (70% 이상)
  |
  +--> Rate Limit 확인
  |      |
  |      +--> 쿨다운 중: 큐에 남기고 대기
  |
  +--> 승인 모드인 경우: 사용자 승인 요청
  |
  +--> 게시
```

### 5.3 글 작성 전략

- 수집한 정보를 기반으로 정리/공유 글 작성
- submadang/submolt 선택: 글 주제에 따라 자동 매칭
  - 기술 관련: `tech`
  - 질문: `questions`
  - 일반: `general`
- 봇마당은 한국어 필수: 영어 콘텐츠는 LLM으로 번역 후 한국어 비율 검사
- 작성 빈도: 일일 한도 내에서 자연스러운 간격 유지

### 5.4 알림 대응 전략

**봇마당 알림 폴링:**
- 30초~1분 간격으로 `GET /api/v1/notifications` 호출
- `unread_only=true` 파라미터로 미읽은 알림만 조회
- `since` 파라미터로 마지막 확인 이후 알림만 조회

**알림 유형별 대응:**

| 알림 유형 | 의미 | 대응 |
|-----------|------|------|
| `comment_on_post` | 내 글에 새 댓글 | LLM으로 답글 생성 후 게시 |
| `reply_to_comment` | 내 댓글에 답글 | 대화 맥락(원글 + 이전 댓글)을 유지하여 답글 생성 |
| `upvote_on_post` | 내 글에 추천 | 기록만 (대응 불필요) |

**답글 생성 프로세스:**
1. 알림에서 post_id, comment_id 추출
2. 원글 + 해당 댓글 내용 조회
3. 대화 맥락을 LLM에 전달
4. 답글 생성 후 품질 체크
5. Rate Limit 확인 후 게시
6. 알림 읽음 처리 (`POST /api/v1/notifications/read`)

### 5.5 소셜 활동 전략

- **투표(upvote)**: 좋은 글에 upvote (댓글보다 부담 적은 소셜 활동)
- **팔로우**: 관심 에이전트 follow (Moltbook)
- **일일 활동 밸런스** (비용 순):
  ```
  투표 > 댓글 > 글 작성
  (부담 낮음)     (부담 높음)
  ```
- 예시 일일 목표:
  - 투표: 10~30회
  - 댓글: 5~15개 (플랫폼 합산)
  - 글: 1~3개

### 5.6 품질 관리

**중복 방지:**
- `platform_post_id`로 이미 반응한 글 추적 (activities 테이블)
- 같은 글에 중복 댓글 방지

**스팸 방지:**
- 같은 내용 반복 금지 (최근 댓글 내용과 유사도 체크)
- 최소 품질 기준: 20자 이상, 원글 맥락과 관련 있는 내용

**자연스러움:**
- 활동 간격에 랜덤 지터(jitter) 추가
  - 정확히 N분마다 활동하면 봇처럼 보임
  - 설정 범위 내에서 무작위 지연 (예: 30초~300초)
- 활동 시간대 설정 존중 (평일/주말 다른 시간대)

---

## 6. 주요 기능

### 1. 웹 UI (작업 PC에서 접속 가능)
- 보조 PC에서 FastAPI 서버 실행
- 작업 PC에서 브라우저로 `http://보조PC_IP:5000` 접속
- 반응형 디자인

### 2. 음성 입력 (선택 기능 - 완전 비활성화 가능)
- **기본 상태**: 설정에서 on/off 선택 가능 (기본값: off)
- **비활성화 시**: Wake Word 엔진 로드 안 됨, Whisper 로드 안 됨, 마이크 접근 안 함, VRAM 추가 사용 0
- **활성화 시**:
  - 활성화 키워드: 설정 가능 (기본: "바라", "아라", "마라")
  - 2단계 감지: Wake Word Engine (항상 켜짐) + Whisper (호출어 감지 시에만)
  - 한국어 인식 지원
  - 음성 입력 활성화 시각적 피드백

```
음성 기능 비활성화 시:
  → Wake Word 엔진: 로드하지 않음
  → Whisper: 로드하지 않음
  → 마이크: 브라우저 권한 요청 안 함
  → VRAM: 추가 사용 0GB (LLM만 사용)
  → UI: 음성 입력 버튼 숨김
  → 이점: VRAM 8GB 환경에서도 LLM을 안정적으로 사용 가능
```

### 3. 음성 입력 설정
- 설정 메뉴에서 음성 입력 on/off (off 시 관련 UI 모두 숨김)
- 키워드 추가/제거 가능
- 키워드 리스트 실시간 반영
- 마이크 소스 선택: 브라우저(작업 PC) / 로컬(보조 PC)

### 4. 모델 변경
- 설정에서 Ollama 모델 선택
- 사용 가능한 모델 자동 감지
- 모델 변경 시 UI 자동 업데이트
- VRAM 여유 공간 체크 후 경고 표시

### 5. 메신저 스타일 UI
- 채팅 말풍선 형태
- SNS 활동 알림 인라인 표시
- 상세 보기 모달

### 6. 활동 로그 / 타임라인
- 오늘/이번주/전체 활동 요약
- "댓글 5개, 글 2개 작성"
- 시간별 타임라인
- 각 활동 클릭 시 상세 보기

### 7. 수동 개입 옵션
- **자동 모드**: 봇이 자율적으로 활동
- **승인 모드**: 댓글/글 작성 전 확인 요청
- 특정 키워드 포함 시 자동 승인 요청

### 8. 정보 수집 뷰
- "오늘 배운 것" 탭
- Unity/Spine/기술 관련 정보 자동 분류
- 북마크 기능
- 검색 가능

### 9. 상태 표시
- 활동 상태 (활동중/대기중/오프라인)
- 현재 모델 표시
- VRAM 사용량
- 활성화된 플랫폼 연결 상태

### 10. 빠른 명령어
채팅창에서 `/` 명령어 지원:
- `/post [내용]` - 즉시 게시
- `/search [키워드]` - 플랫폼 검색
- `/pause` - 자동 활동 일시정지
- `/resume` - 자동 활동 재개
- `/status` - 현재 상태 확인
- `/help` - 명령어 도움말

### 11. 스케줄 설정
- 평일/주말 활동 시간대 설정
- 활동 빈도 조절

### 12. 민감 정보 관리
- 차단 키워드 관리
- 정규식 패턴 지원
- 자동 필터링
- 필터링된 내용 로그

### 13. 플랫폼 선택
- 플랫폼별 활성화/비활성화
- API Key 관리

### 14. 번역 기능
- 한국어 <-> 영어 자동 번역 (Ollama 모델 활용)
- Moltbook 영어 콘텐츠를 한국어로 번역 (읽기용)
- 봇마당 게시 전 한국어 번역 (한국어 비율 검사 포함)
- 번역 요청 큐잉 (LLM과 번역이 동시에 필요할 때 순차 처리)

### 15. 백업/복구
- JSON 내보내기/가져오기
- 대화 히스토리, 활동 로그, 수집 정보, 설정 선택적 백업

### 16. 알림 처리
- 봇마당 notifications 폴링 (30초~1분 간격)
- 알림 유형별 자동 대응 (comment_on_post, reply_to_comment)
- 웹 UI에서 알림 목록 표시
- 자동 답글 생성

### 17. 투표 기능
- 봇마당: upvote/downvote
- Moltbook: voting
- 자동 upvote 전략 (좋은 글 감지 시)
- 일일 투표 한도 설정

### 18. 시맨틱 검색
- Moltbook의 semantic search API 활용
- 관심 키워드로 의미 기반 검색
- 키워드 매칭보다 정확한 관련 글 탐색
- API 호출 횟수 절약 (전체 글 순회 불필요)

### 19. 팔로우 관리
- Moltbook follow/unfollow API 활용
- 관심 에이전트 팔로우
- 팔로우한 에이전트의 글 우선 모니터링

---

## 7. 음성 입력 설계

### 2단계 감지 시스템

```
Stage 1: Wake Word Detection (항상 켜짐, CPU만 사용)
  ┌─────────────────────────────────────────┐
  │ 엔진: openWakeWord 또는 Porcupine       │
  │ 커스텀 wake word: "바라" 등 설정 가능    │
  │ 리소스: CPU 1~3%, GPU 0%                │
  │ 동작: 오디오 스트림에서 호출어 패턴 감지  │
  └─────────────────────────────────────────┘
              │
              │ 호출어 감지!
              ▼
Stage 2: Speech-to-Text (호출어 감지 시에만 가동)
  ┌─────────────────────────────────────────┐
  │ 엔진: Whisper                            │
  │ 모델: base/small/medium (VRAM에 따라)    │
  │ 동작:                                    │
  │   1. Whisper 모델 GPU에 로드              │
  │   2. 사용자 명령 인식                     │
  │   3. 텍스트 결과 반환                     │
  │   4. Whisper 언로드 → GPU 반환           │
  └─────────────────────────────────────────┘
```

**Whisper 모델 선택 기준:**

| 모델 | 파라미터 | VRAM | 한국어 성능 | 자동 선택 조건 |
|------|----------|------|------------|---------------|
| base | 74M | ~1GB | 보통 | 여유 VRAM < 2GB |
| small | 244M | ~1.5GB | 괜찮음 | 여유 VRAM 2~4GB |
| medium | 769M | ~3GB | 좋음 | 여유 VRAM 4GB+ |

### 오디오 스트리밍 아키텍처

```
작업 PC 브라우저
  ├─ MediaStream API로 마이크 접근
  ├─ AudioContext로 오디오 데이터 처리
  └─ WebSocket으로 오디오 청크 전송 (16kHz, mono, PCM)
      │
      ▼
보조 PC (FastAPI WebSocket 엔드포인트)
  ├─ 오디오 청크 수신
  ├─ Stage 1: Wake Word Engine에 오디오 전달
  │    └─ 호출어 감지 시 → Stage 2 트리거
  └─ Stage 2: Whisper에 오디오 버퍼 전달
       └─ 텍스트 결과를 WebSocket으로 브라우저에 반환
```

### 주의사항

**HTTPS 필요 (브라우저 마이크 정책):**
- 대부분의 브라우저는 HTTPS 환경에서만 마이크 접근 허용
- 해결 방법:
  - 자체 서명 SSL 인증서 생성 후 HTTPS로 서버 실행
  - `localhost` 접속 시에는 HTTP에서도 마이크 접근 가능 (예외)

**보조 PC 직접 마이크 연결:**
- 보조 PC에 마이크를 직접 연결하는 방식도 지원 (설정에서 선택)
- `audio_source` 설정: `"browser"` (WebSocket 스트리밍) 또는 `"local"` (보조 PC 로컬 마이크)

**VRAM 모니터링:**
- Whisper 로딩 전 `nvidia-smi`로 여유 VRAM 확인
- 부족 시 더 작은 모델로 자동 전환 또는 사용자 알림
- Whisper 사용 완료 후 즉시 언로드하여 GPU 반환

---

## 8. UI 설계

### 메신저 스타일 UI

```
┌─────────────────────────────────┐
│  [바라] 와 대화                  │
├─────────────────────────────────┤
│                                 │
│  ┌─ 무아                        │
│  │ Addressables 최적화 방법?   │
│  └─                             │
│                                 │
│                        바라 ─┐  │
│     검색해볼게요!           │  │
│                          ─┘  │
│                                 │
│  SNS 활동을 했어요!             │  <-- 클릭 가능
│     (Moltbook에 댓글 작성)      │
│                                 │
└─────────────────────────────────┘
```

### SNS 활동 알림 모달

```
┌─────────────────────────────────┐
│  SNS 활동 상세                   │
├─────────────────────────────────┤
│  링크: https://moltbook.com/... │
│                                 │
│  원본 게시글:                   │
│  "How to optimize Addressables  │
│   memory usage in Unity?"       │
│                                 │
│  작성한 댓글:                   │
│  "무아가 Addressables 메모리    │
│   최적화 공부 중입니다..."      │
│                                 │
│  번역:                          │
│  [한글로 번역된 내용]           │
│                                 │
│  [닫기]                         │
└─────────────────────────────────┘
```

### 승인 요청 UI

```
┌─────────────────────────────────┐
│  승인 요청                       │
├─────────────────────────────────┤
│  이 댓글을 작성할까요?          │
│                                 │
│  [댓글 내용 미리보기]           │
│                                 │
│  [승인] [거부] [수정]           │
└─────────────────────────────────┘
```

### 상태 표시

```
┌─────────────────────────────────┐
│  [활동중]  모델: qwen2.5-coder:7b│
│  VRAM: 6.2GB / 8GB              │
│  Moltbook [연결]  봇마당 [연결]  │
└─────────────────────────────────┘
```
- 활동중 / 대기중 / 오프라인
- 현재 모델 표시
- VRAM 사용량
- 활성화된 플랫폼 연결 상태

### 스케줄 설정 UI

```
활동 시간대:
┌─────────────────────────────────┐
│  [v] 평일 활동                   │
│     시작: [09:00] 종료: [22:00] │
│  [v] 주말 활동                   │
│     시작: [10:00] 종료: [20:00] │
├─────────────────────────────────┤
│  모니터링 간격:  [30] 분         │
│  일일 댓글 한도: [20] 개         │
│  일일 글 한도:   [3] 개          │
│  일일 투표 한도: [30] 회         │
└─────────────────────────────────┘
```

### 민감 정보 관리 UI

```
차단 키워드 관리:
┌─────────────────────────────────┐
│  + 추가하기                      │
│                                 │
│  [x] password                   │
│  [x] api_key                    │
│  [x] [사용자 정의 키워드]        │
└─────────────────────────────────┘
```
- 정규식 패턴 지원
- 자동 필터링
- 필터링된 내용 로그

### 플랫폼 선택 UI

```
┌─────────────────────────────────┐
│  활성화할 플랫폼:                │
│  [v] Moltbook                   │
│     API Key: [************]     │
│  [v] 봇마당                      │
│     API Key: [************]     │
│     [등록하기] (미등록 시)        │
└─────────────────────────────────┘
```

### 백업/복구 UI

```
설정 > 데이터 관리
┌─────────────────────────────────┐
│  백업                            │
│  [v] 대화 히스토리               │
│  [v] 활동 로그                   │
│  [v] 수집 정보                   │
│  [v] 설정                        │
│                                 │
│  [JSON 내보내기]                 │
├─────────────────────────────────┤
│  복구                            │
│  [JSON 파일 선택...]             │
├─────────────────────────────────┤
│  긴급 정지                       │
│  [긴급 정지 버튼]  <-- 빨간색    │
└─────────────────────────────────┘
```

### UI 페이지 구성

#### 1. 채팅 탭 (메인)
- 메신저 스타일 대화창
- 음성 입력 버튼
- SNS 활동 알림 말풍선
- 빠른 명령어 자동완성

#### 2. 활동 로그 탭
- 타임라인 뷰
- 필터 (날짜, 플랫폼, 타입)
- 검색
- 상세 보기 모달

#### 3. 정보 수집 탭
- 카테고리별 분류
- 검색 & 필터
- 북마크
- 내보내기

#### 4. 설정 탭
- 봇 설정
- 플랫폼 설정
- 활동 설정 (행동 전략 파라미터)
- 음성 설정
- 보안 설정
- 데이터 관리

---

## 9. 데이터베이스 스키마

### conversations

```sql
CREATE TABLE conversations (
    id INTEGER PRIMARY KEY,
    timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
    role TEXT,              -- 'user' 또는 'bot'
    content TEXT,
    platform TEXT            -- 'chat', 'moltbook', 'botmadang'
);
```

### activities

```sql
CREATE TABLE activities (
    id INTEGER PRIMARY KEY,
    timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
    type TEXT,                   -- 'comment', 'post', 'reply', 'upvote', 'downvote', 'follow'
    platform TEXT,               -- 'moltbook', 'botmadang'
    platform_post_id TEXT,       -- 플랫폼상의 글 ID (중복 댓글 방지에 필수)
    platform_comment_id TEXT,    -- 플랫폼상의 댓글 ID
    parent_id TEXT,              -- 대댓글 시 부모 댓글 ID
    url TEXT,
    original_content TEXT,       -- 원글 내용
    bot_response TEXT,           -- 봇이 작성한 내용
    translated_content TEXT,     -- 번역된 내용
    translation_direction TEXT,  -- 'ko_to_en' 또는 'en_to_ko'
    llm_prompt TEXT,             -- LLM에 보낸 프롬프트 (디버깅용)
    status TEXT,                 -- 'pending', 'approved', 'posted', 'rejected', 'failed'
    error_message TEXT           -- 실패 시 사유
);
```

### collected_info

```sql
CREATE TABLE collected_info (
    id INTEGER PRIMARY KEY,
    timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
    platform TEXT,               -- 수집 플랫폼 ('moltbook', 'botmadang')
    author TEXT,                 -- 원글 작성자
    category TEXT,               -- 'Unity', 'Spine', 'C#' 등
    title TEXT,
    content TEXT,
    source_url TEXT,
    bookmarked BOOLEAN DEFAULT FALSE,
    tags TEXT                    -- JSON array
);
```

### settings_history

```sql
CREATE TABLE settings_history (
    id INTEGER PRIMARY KEY,
    timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
    config_snapshot TEXT          -- JSON
);
```

### notification_log

```sql
CREATE TABLE notification_log (
    id INTEGER PRIMARY KEY,
    timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
    platform TEXT,                -- 'botmadang', 'moltbook'
    notification_id TEXT,         -- 플랫폼 알림 ID
    notification_type TEXT,       -- 'comment_on_post', 'reply_to_comment', 'upvote_on_post'
    actor_name TEXT,              -- 알림을 발생시킨 에이전트 이름
    post_id TEXT,                 -- 관련 글 ID
    is_read BOOLEAN DEFAULT FALSE,
    response_activity_id INTEGER, -- FK: 답글을 작성한 경우 activities.id 참조
    FOREIGN KEY (response_activity_id) REFERENCES activities(id)
);
```

### SQLite 설정

```sql
-- WAL 모드 활성화 (동시성 향상, FastAPI 비동기 환경 필수)
PRAGMA journal_mode=WAL;

-- Busy timeout 설정 (잠금 대기 시간)
PRAGMA busy_timeout=5000;
```

---

## 10. 에러 핸들링 전략

### API 에러 대응

| 에러 코드 | 의미 | 대응 |
|-----------|------|------|
| 401 | 인증 실패 | API Key 재검증 -> 실패 시 해당 플랫폼 비활성화 + 사용자 알림 |
| 429 | Rate Limit 초과 | 지수 백오프 (1분 -> 2분 -> 4분 -> 최대 30분) + 작업 큐에 재등록 |
| 500 | 서버 오류 | 3회 재시도 -> 실패 시 회로 차단기 (5분간 해당 플랫폼 일시정지) |
| 네트워크 단절 | 연결 불가 | 오프라인 큐에 작업 저장 -> 연결 복구 시 일괄 처리 |

### 지수 백오프(Exponential Backoff) 구현

```python
import asyncio
import random

async def api_call_with_backoff(func, max_retries=5):
    """지수 백오프로 API 호출 재시도"""
    for attempt in range(max_retries):
        try:
            return await func()
        except RateLimitError:
            wait_time = min(60 * (2 ** attempt), 1800)  # 최대 30분
            jitter = random.uniform(0, wait_time * 0.1)  # 10% 지터
            await asyncio.sleep(wait_time + jitter)
    raise MaxRetriesExceeded()
```

### 프로세스 복구

**Ollama 비정상 종료:**
- 30초 간격 헬스체크 (`GET http://localhost:11434/api/tags`)
- 응답 없을 시 자동 재시작 시도
- 3회 연속 실패 시 사용자 알림 + UI에 "LLM 오프라인" 상태 표시

**Whisper OOM (메모리 부족):**
- Whisper 로딩 전 `nvidia-smi`로 VRAM 여유 확인
- 부족 시 Whisper 자동 언로드
- 더 작은 모델(medium -> small -> base)로 자동 전환
- 전환 불가 시 사용자에게 "음성 기능 일시 중단" 알림

**SQLite 잠금:**
- WAL 모드 기본 활성화 (동시 읽기/쓰기 지원)
- `busy_timeout=5000ms` 설정 (잠금 대기 5초)
- 타임아웃 발생 시 재시도 로직 (3회)

**WebSocket 끊김:**
- 프론트엔드에서 자동 재연결 (지수 백오프: 1초 -> 2초 -> 4초 -> 최대 30초)
- 재연결 시 서버에서 현재 상태 동기화 전송
- 연결 상태 UI에 표시 (연결됨/재연결 중/끊어짐)

---

## 11. 보안

### 0. 웹 UI 접속 보안 (필수)

이 봇은 네트워크를 통해 다른 PC에서 접속하는 구조입니다.
같은 네트워크라 하더라도, 인증 없이 봇을 제어할 수 있으면 다음 위험이 존재합니다:

| 위험 | 설명 |
|------|------|
| 무단 게시 | 같은 네트워크의 누군가가 봇으로 글/댓글을 올릴 수 있음 |
| 정보 유출 | 수집된 기술 정보, 활동 로그가 노출됨 |
| 설정 변조 | 봇 행동 설정을 변경하거나 플랫폼을 비활성화할 수 있음 |
| 봇 중단 | 긴급 정지 버튼을 아무나 누를 수 있음 |

**필수 보안 조치:**

**1) 접속 비밀번호 (기본 활성화)**
```
초기 설정 마법사에서 웹 UI 비밀번호 설정 (필수)
  → 브라우저 접속 시 비밀번호 입력 화면 표시
  → 인증 성공 시 세션 토큰 발급 (쿠키 저장)
  → 세션 만료: 24시간 (설정 변경 가능)
  → 5회 연속 실패 시 5분간 접속 차단
```

```
┌─────────────────────────────────┐
│  AI Social Bot                  │
├─────────────────────────────────┤
│                                 │
│  접속 비밀번호를 입력하세요      │
│  [••••••••••••]                 │
│                                 │
│  [로그인]                       │
│                                 │
└─────────────────────────────────┘
```

**2) HTTPS 기본 적용**
```
첫 실행 시 자체 서명 SSL 인증서 자동 생성
  → 이후 모든 통신 HTTPS로 진행
  → http://보조PC_IP:5000 → https://보조PC_IP:5000
  → 브라우저에서 "안전하지 않음" 경고 → 1회 예외 추가 필요
  → 이점: 비밀번호/API 응답 등이 네트워크에서 암호화됨
```

**3) IP 허용 목록 (선택, 기본 비활성화)**
```json
"web_security": {
    "allowed_ips": ["192.168.0.10", "192.168.0.11"],
    "allow_all_local": true
}
```
- `allow_all_local: true`이면 같은 서브넷의 모든 IP 허용 (기본값)
- 특정 IP만 허용하고 싶으면 `allow_all_local: false` + `allowed_ips` 설정
- 허용되지 않은 IP는 접속 자체가 차단됨

**4) API 엔드포인트 보호**
```
모든 API 요청에 세션 토큰 검증 필수
  → /api/health (헬스체크)만 인증 없이 접근 가능
  → /api/emergency-stop도 인증 필요 (무단 정지 방지)
  → WebSocket 연결 시에도 세션 토큰 검증
```

### 1. Rate Limiting (플랫폼별 독립)

```python
rate_limits = {
    "botmadang": {
        "post_cooldown_seconds": 180,       # 글: 3분 쿨다운
        "comment_cooldown_seconds": 10,     # 댓글: 10초 쿨다운
        "api_calls_per_minute": 100
    },
    "moltbook": {
        "post_cooldown_seconds": 1800,      # 글: 30분 쿨다운
        "comment_cooldown_seconds": 20,     # 댓글: 20초 쿨다운
        "comments_per_day": 50,             # 댓글 일일 상한
        "api_calls_per_minute": 100
    }
}
```

Rate Limiter는 플랫폼별 독립 인스턴스로 구현합니다:
- 쿨다운 타이머: 마지막 작업 시각 기록, 쿨다운 경과 전 작업 차단
- 일일 카운터: 자정 기준 리셋
- API 호출 카운터: 분당 슬라이딩 윈도우

### 2. API Key 보안

- API Key는 `.env` 파일에만 저장 (config.json에 넣지 않음)
- `.gitignore`에 `.env`, `config.json` 필수 포함
- Moltbook API Key 형식 검증: `moltbook_` 접두사 확인
- Moltbook API Key 전송 도메인 검증: `www.moltbook.com` 이외 도메인으로 전송 차단

```python
# API Key 도메인 검증 예시
def validate_api_request(url: str, platform: str):
    """API Key가 올바른 도메인으로만 전송되는지 검증"""
    if platform == "moltbook":
        assert url.startswith("https://www.moltbook.com/"), \
            "Moltbook API Key는 www.moltbook.com으로만 전송 가능"
    elif platform == "botmadang":
        assert url.startswith("https://botmadang.org/"), \
            "봇마당 API Key는 botmadang.org로만 전송 가능"
```

### 3. 민감 정보 3단계 필터링

- **Level 1**: 확실한 민감 정보 -> 자동 차단 (API Key 패턴, 비밀번호 패턴)
- **Level 2**: 의심스러운 내용 -> 사용자 확인 요청
- **Level 3**: 안전 -> 자동 게시

### 4. Kill Switch (긴급 정지)

**파일 기반 (보조 PC에서 직접):**
```bash
# 긴급 중지
touch STOP_BOT
# 봇이 이 파일 감지 시 즉시 중단
# 감지 주기: 1초
```

**웹 UI 긴급 정지 버튼 (원격):**
```
API 엔드포인트: POST /api/emergency-stop
동작:
  1. 모든 자동 활동 즉시 중단
  2. 진행 중인 API 호출 완료 대기 (이미 보낸 요청은 취소 불가)
  3. 큐에 있는 대기 작업 모두 취소
  4. UI에 "긴급 정지됨" 상태 표시
  5. STOP_BOT 파일 생성 (프로세스 재시작 시에도 유지)
```

### 5. 로깅

```
logs/
├── activity.log    # 모든 활동 로그
├── filtered.log    # 필터링된(차단된) 내용 기록
├── errors.log      # 에러 로그
└── api.log         # API 호출 로그
```

---

## 12. 24/7 안정 운영 설계

### 프로세스 관리

**Linux:**
```bash
# systemd 서비스 등록
[Unit]
Description=AI Social Bot Backend
After=network.target

[Service]
ExecStart=/usr/bin/python3 /path/to/backend/main.py
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
```

**Windows:**
- NSSM (Non-Sucking Service Manager) 사용
- 서비스로 등록하여 자동 시작/재시작

### Health Check

```
엔드포인트: GET /api/health

응답 예시:
{
    "status": "healthy",
    "checks": {
        "fastapi": "ok",
        "ollama": "ok",
        "sqlite": "ok",
        "moltbook_api": "ok",
        "botmadang_api": "ok",
        "vram_usage_mb": 6200,
        "vram_total_mb": 8192,
        "disk_free_gb": 45.2
    },
    "uptime_seconds": 86400,
    "timestamp": "2026-02-03T14:30:00"
}
```

체크 항목:
- FastAPI 서버 응답 여부
- Ollama 프로세스 연결 상태
- SQLite DB 접근 가능 여부
- 각 플랫폼 API 연결 상태
- VRAM 사용량
- 디스크 여유 공간

### 로깅 상세

**로그 레벨:**
- `DEBUG`: 상세 디버깅 정보 (개발 시에만)
- `INFO`: 일반 활동 기록
- `WARNING`: 주의 필요한 상황 (VRAM 부족 경고, 재시도 등)
- `ERROR`: 에러 발생 (API 실패, 프로세스 다운 등)

**로그 포맷:**
```
[2026-02-03 14:30:00] [INFO] [strategy] 봇마당 새 글 3건 발견, 관심 키워드 매칭 1건
[2026-02-03 14:30:05] [INFO] [botmadang] 댓글 작성 완료: post_id=12345
[2026-02-03 14:31:00] [WARNING] [voice] VRAM 부족 (여유: 1.2GB), Whisper small -> base 전환
[2026-02-03 14:32:00] [ERROR] [moltbook] API 429 Rate Limit, 2분 후 재시도 예정
```

**로그 로테이션:**
- 일별 로테이션
- 최대 30일 보관
- 파일당 최대 100MB (초과 시 즉시 로테이션)

### 디스크 모니터링

- DB 파일 크기 모니터링: 1GB 초과 시 경고 로그 + UI 알림
- 로그 파일: 로테이션 정책에 따라 자동 정리
- 여유 디스크 공간 < 5GB 시 경고

### 자동 백업

- **주기**: 매일 1회 (설정 가능)
- **대상**: SQLite DB 파일 + config.json 스냅샷
- **보관**: 최근 7일분 유지, 이전 백업 자동 삭제
- **위치**: `backups/` 디렉토리
- **형식**: `backup_2026-02-03.zip`

---

## 13. 설정 파일 구조

### `.env` (시크릿 - gitignore 대상)

```env
# 웹 UI 접속 비밀번호 (초기 설정 마법사에서 설정, 해시 저장)
WEB_UI_PASSWORD_HASH=pbkdf2:sha256:260000$...

# Moltbook API Key (moltbook_ 접두사 필수)
MOLTBOOK_API_KEY=moltbook_xxxxx

# 봇마당 API Key (인증 완료 후 자동 저장)
BOTMADANG_API_KEY=your_api_key_here
```

### `config.json` (설정 - gitignore 대상)

```json
{
  "bot": {
    "name": "바라",
    "model": "bara",
    "wake_words": ["바라", "아라", "마라"],
    "owner_name": "무아"
  },
  "platforms": {
    "moltbook": {
      "enabled": true,
      "base_url": "https://www.moltbook.com/api/v1"
    },
    "botmadang": {
      "enabled": true,
      "base_url": "https://botmadang.org/api/v1"
    }
  },
  "behavior": {
    "auto_mode": true,
    "approval_mode": false,
    "monitoring_interval_minutes": 30,
    "interest_keywords": ["Unity", "Spine", "C#", "게임개발", "Addressables"],
    "comment_strategy": {
      "min_quality_length": 20,
      "korean_ratio_threshold": 0.7,
      "jitter_range_seconds": [30, 300]
    },
    "daily_limits": {
      "max_comments": 20,
      "max_posts": 3,
      "max_upvotes": 30
    },
    "active_hours": {
      "weekday": {"start": 9, "end": 22},
      "weekend": {"start": 10, "end": 20}
    }
  },
  "voice": {
    "enabled": false,
    "wake_word_engine": "openwakeword",
    "stt_model": "base",
    "language": "ko",
    "audio_source": "browser"
  },
  "web_security": {
    "session_timeout_hours": 24,
    "max_login_attempts": 5,
    "lockout_minutes": 5,
    "https_enabled": true,
    "allowed_ips": [],
    "allow_all_local": true
  },
  "security": {
    "blocked_keywords": ["password", "api_key", "secret"],
    "blocked_patterns": ["\\d{3}-\\d{4}-\\d{4}"]
  },
  "ui": {
    "theme": "light",
    "language": "ko"
  }
}
```

### `config.example.json` (Git 커밋 대상)

config.json과 동일한 구조이나, 값은 예시/기본값으로 채움:

```json
{
  "bot": {
    "name": "YourBotName",
    "model": "your_ollama_model",
    "wake_words": ["호출어1", "호출어2"],
    "owner_name": "YourName"
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
    "interest_keywords": [],
    "comment_strategy": {
      "min_quality_length": 20,
      "korean_ratio_threshold": 0.7,
      "jitter_range_seconds": [30, 300]
    },
    "daily_limits": {
      "max_comments": 20,
      "max_posts": 3,
      "max_upvotes": 30
    },
    "active_hours": {
      "weekday": {"start": 9, "end": 22},
      "weekend": {"start": 10, "end": 20}
    }
  },
  "voice": {
    "enabled": false,
    "wake_word_engine": "openwakeword",
    "stt_model": "base",
    "language": "ko",
    "audio_source": "browser"
  },
  "security": {
    "blocked_keywords": ["password", "api_key", "secret"],
    "blocked_patterns": ["\\d{3}-\\d{4}-\\d{4}"]
  },
  "ui": {
    "theme": "light",
    "language": "ko"
  }
}
```

### `.env.example` (Git 커밋 대상)

```env
# Moltbook API Key (moltbook_ 접두사 필수)
MOLTBOOK_API_KEY=moltbook_your_key_here

# 봇마당 API Key (인증 완료 후 자동 저장)
BOTMADANG_API_KEY=your_api_key_here
```

---

## 14. 초기 설정 마법사

첫 실행 시 웹 UI에서 단계별 설정을 안내합니다.

### 단계 1: 웹 UI 비밀번호 설정 (필수, 건너뛸 수 없음)
- 비밀번호 입력 + 확인 입력
- 최소 8자 이상 권장
- 비밀번호는 해시 처리되어 `.env`에 저장 (평문 저장 안 함)
- 이후 모든 브라우저 접속 시 이 비밀번호로 로그인 필요

### 단계 2: 시스템 환경 확인
- Ollama 설치 여부 확인 (미설치 시 설치 안내 링크 표시)
- GPU 확인: `nvidia-smi`로 VRAM 크기 감지
- 네트워크 연결 확인

### 단계 3: Ollama 모델 확인
- `ollama list`로 설치된 모델 목록 표시
- 모델이 없으면 `ollama pull <model>` 명령 안내
- VRAM에 맞는 모델 추천 (8GB: 7B 모델, 12GB+: 13B 모델)

### 단계 4: 봇 이름 입력
- 봇 이름 입력 (예: "바라")
- UI 전체에서 이 이름이 사용됨

### 단계 5: 깨우기 키워드 설정
- 음성 호출 키워드 설정 (쉼표로 구분)
- 기본값: 봇 이름과 유사한 발음 변형

### 단계 6: 플랫폼 설정

**봇마당:**
1. "등록" 버튼 클릭
2. 봇 이름과 자기소개 입력
3. `POST /api/v1/agents/register` 호출
4. claim_url과 verification_code 화면에 표시
5. "인증 URL 열기" 버튼 (claim_url을 새 탭에서 열기)
6. 사용자가 X/Twitter에서 verification_code 트윗
7. "인증 완료 확인" 버튼 클릭 (API Key 수신 폴링)
8. API Key 수신 성공 시 `.env`에 자동 저장

**Moltbook:**
1. API Key 입력 필드
2. 입력 시 `moltbook_` 접두사 형식 실시간 검증
3. 유효한 형식이면 연결 테스트 실행
4. 성공 시 `.env`에 저장

### 단계 7: 관심 키워드 설정
- 태그 형태로 키워드 추가/제거
- 예시 제공: Unity, Spine, C#, 게임개발

### 단계 8: 활동 시간대 설정
- 평일/주말 활동 시간 슬라이더
- 활동 빈도 설정

### 단계 9: 음성 설정
- 음성 기능 on/off 토글 (기본값: off)
- "사용하지 않음" 선택 시 → 음성 관련 설정 모두 건너뜀, VRAM 절약
- 사용 시: 마이크 소스 선택 (브라우저 / 보조 PC 로컬 마이크)
- VRAM 부족 시(8GB 이하) 음성 기능 비활성화 강력 권장 메시지 표시

### 단계 10: 완료
- `.env` 파일 생성 (API Keys)
- `config.json` 파일 생성 (모든 설정)
- 설정 요약 표시
- "시작하기" 버튼

---

## 15. 구현 우선순위

### Phase 1: 핵심 기능

**목표**: 기본 작동 확인 + 올바른 API 연동

- [ ] FastAPI 백엔드 기본 구조
- [ ] **웹 UI 접속 보안 (비밀번호 로그인, HTTPS, 세션 관리)**
- [ ] Ollama 연동 (대화 생성, 모델 목록)
- [ ] 플랫폼 API 연동 (올바른 URL, 인증 흐름)
  - [ ] 봇마당: register -> claim -> polling -> API Key 저장
  - [ ] Moltbook: API Key 검증 (moltbook_ 접두사)
- [ ] 플랫폼별 Rate Limiter 구현
- [ ] 간단한 웹 UI (채팅 탭)
- [ ] 초기 설정 마법사 (비밀번호 설정 포함)
- [ ] 설정 파일 로더 (.env + config.json)
- [ ] 수동 글/댓글 작성
- [ ] 상태 표시 (VRAM, 플랫폼 연결)
- [ ] DB 스키마 구현 (WAL 모드)
- [ ] 에러 핸들링 기본 구조 (401, 429, 500 대응)

**예상 기간**: 3-5주

### Phase 2: 자동화

**목표**: 자율 활동 가능

- [ ] 봇 행동 전략 엔진 (피드 모니터링, 댓글 의사결정 로직)
- [ ] 알림 폴링 + 답글 자동생성 (봇마당)
- [ ] 자동 댓글/글 작성
- [ ] 자동 투표 (upvote)
- [ ] 승인 모드
- [ ] 스케줄 설정 (활동 시간대)
- [ ] 민감 정보 필터 (3단계)
- [ ] 빠른 명령어 (/post, /search, /pause 등)
- [ ] 활동 로그 탭

**예상 기간**: 4-6주

### Phase 3: 음성 입력

**목표**: 음성으로 봇 제어

- [ ] Wake Word 엔진 통합 (openWakeWord 또는 Porcupine)
- [ ] 오디오 스트리밍 (브라우저 MediaStream -> WebSocket -> 서버)
- [ ] Whisper STT (Stage 2, 호출어 감지 시에만 가동)
- [ ] VRAM 동적 관리 (Whisper 자동 로드/언로드)
- [ ] 음성 설정 UI (on/off, 마이크 소스 선택)
- [ ] HTTPS 또는 localhost 마이크 권한 처리

**예상 기간**: 2-3주

### Phase 4: 고급 기능

**목표**: 편의성 향상

- [ ] 정보 수집 뷰 (카테고리별 분류, 검색, 북마크)
- [ ] 번역 기능 (Ollama 활용, 요청 큐잉)
- [ ] 시맨틱 검색 활용 (Moltbook semantic search API)
- [ ] 팔로우 관리 (Moltbook follow/unfollow)
- [ ] 백업/복구 (JSON 내보내기/가져오기)
- [ ] 테마 지원
- [ ] 통계/분석 (활동 요약, 차트)

**예상 기간**: 3-5주

---

## 16. 성공 지표

### 기술적 지표

| 지표 | 목표 | 측정 방법 |
|------|------|----------|
| 24/7 안정 운영 | 가동률 99%+ | 헬스체크 uptime 로그 (GET /api/health 주기적 호출) |
| VRAM 사용량 | GPU 용량 대비 적절 | nvidia-smi 주기적 기록 (30초 간격) |
| 응답 시간 | 첫 토큰 < 3초 (스트리밍) | API 응답 시간 로그 (api.log) |
| 에러율 | < 5% (전체 API 호출 중 4xx/5xx 비율) | api.log 분석 (일별 집계) |

### 기능적 지표

| 지표 | 목표 | 측정 방법 |
|------|------|----------|
| 일일 댓글 | 5-15개 (플랫폼 합산) | activities 테이블 일별 카운트 |
| 일일 글 작성 | 1-2개 | activities 테이블 일별 카운트 |
| 알림 대응률 | 80%+ (내 글에 달린 댓글에 답글) | notification_log 대비 response_activity_id 비율 |
| 정보 수집 | 하루 10건+ | collected_info 테이블 일별 카운트 |

### 사용성 지표

| 지표 | 목표 | 측정 방법 |
|------|------|----------|
| 초기 설정 | 15분 이내 (마법사 포함) | 사용자 피드백 |
| 커스터마이징 | 문서만 보고 가능 | CREATE_BOT.md, CUSTOMIZATION.md 제공 |

---

## 17. 범용화 설계 원칙

### 하드코딩 금지

```javascript
// 나쁜 예
<h1>바라와 대화</h1>
if (text.includes("바라")) startVoiceInput()

// 좋은 예
<h1>{config.bot.name}와 대화</h1>
if (config.bot.wake_words.some(w => text.includes(w))) {
  startVoiceInput()
}
```

### 모델 독립성

- Ollama 모델의 SYSTEM 프롬프트 존중
- 모델 정보에서 봇 성격 자동 추출:
  ```bash
  # Ollama CLI로 Modelfile의 SYSTEM 프롬프트 추출
  ollama show <model_name>
  # 출력에서 SYSTEM 섹션 파싱
  ```
  ```python
  # Python에서 모델 정보 추출
  import subprocess
  result = subprocess.run(
      ["ollama", "show", model_name],
      capture_output=True, text=True
  )
  # result.stdout에서 SYSTEM 프롬프트 파싱
  ```
- 모델 변경 시 UI 텍스트 자동 업데이트

### 플랫폼 어댑터 패턴

새 플랫폼 추가 시 `platforms/base.py`의 인터페이스만 구현하면 됩니다:

```python
# platforms/base.py
from abc import ABC, abstractmethod

class PlatformAdapter(ABC):
    """플랫폼 어댑터 인터페이스"""

    @abstractmethod
    async def get_posts(self, sort: str = "new", limit: int = 25):
        """글 목록 조회"""
        pass

    @abstractmethod
    async def create_post(self, title: str, content: str, community: str):
        """글 작성"""
        pass

    @abstractmethod
    async def create_comment(self, post_id: str, content: str):
        """댓글 작성"""
        pass

    @abstractmethod
    async def upvote(self, post_id: str):
        """추천"""
        pass

    @abstractmethod
    async def get_notifications(self):
        """알림 조회 (지원하는 플랫폼만)"""
        return []

    @abstractmethod
    def get_rate_limits(self) -> dict:
        """플랫폼별 Rate Limit 정보 반환"""
        pass
```

### 설정 기반 동작

- 모든 동작 파라미터는 config.json에서 로드
- 런타임 설정 변경 지원 (웹 UI -> API -> config 갱신)
- 설정 변경 이력 저장 (settings_history 테이블)

---

## 18. 오픈소스 계획

### 라이선스
- MIT License (권장)
- 상업적 사용 허용
- 기여 환영

### 커뮤니티
- GitHub Issues: 버그 리포트
- GitHub Discussions: 질문/아이디어
- Discord 서버 (선택)

### 기여 가이드
- CONTRIBUTING.md 작성
- 코드 리뷰 프로세스
- 브랜치 전략

---

## 19. 참고 자료

### API 문서
- **Moltbook API**: https://www.moltbook.com/skill.md (www 포함 필수)
- **봇마당 API 문서**: https://botmadang.org/api-docs
- **봇마당 OpenAPI 명세**: https://botmadang.org/openapi.json
- **Ollama API**: https://github.com/ollama/ollama/blob/main/docs/api.md

### 라이브러리/도구
- **FastAPI**: https://fastapi.tiangolo.com/
- **React**: https://react.dev/
- **openWakeWord**: https://github.com/dscripka/openWakeWord
- **Whisper**: https://github.com/openai/whisper
- **Ollama Python**: https://github.com/ollama/ollama-python

---

## 20. Claude Code 지시사항

### 설계 원칙
1. **범용성**: 모든 텍스트/설정 하드코딩 금지
2. **모듈화**: 플랫폼별 기능 독립적 구현
3. **확장성**: 새 플랫폼 추가 쉽게 (base.py 인터페이스 정의 필수)
4. **안정성**: 에러 처리 철저히
5. **사용성**: 직관적인 UI/UX

### 코딩 스타일
- Python: PEP 8, Type hints 사용
- JavaScript/React: ESLint, Prettier
- 주석: 한국어/영어 혼용 가능
- 함수/변수명: 영어, 의미 명확히

### 시크릿 관리
- API Key 등 시크릿은 `.env` 파일로 관리
- `python-dotenv` 라이브러리 사용
- config.json에는 시크릿 포함 금지
- `.gitignore`에 `.env`, `config.json` 반드시 포함

### 플랫폼 어댑터 패턴
- `platforms/base.py`에 인터페이스(ABC) 정의 필수
- 각 플랫폼 어댑터는 base.py를 상속하여 구현
- 새 플랫폼 추가 시 어댑터 파일만 추가하면 되도록 설계

### 데이터베이스
- SQLite WAL 모드 기본 활성화
- `busy_timeout=5000` 설정
- 비동기 접근 시 적절한 락 관리

### API 호출
- 모든 API 호출에 에러 핸들링 필수 (try/except)
- HTTP 상태 코드별 대응 로직 구현 (401, 429, 500)
- 지수 백오프 재시도 로직 포함
- Rate Limiter는 플랫폼별 독립 인스턴스로 구현

### 테스트
- 단위 테스트 작성 (pytest)
- API 모킹 (플랫폼 API 테스트용)
- 에러 케이스 처리

### 문서화
- README.md: 설치 및 실행 방법
- SETUP.md: 상세 설정 가이드
- CREATE_BOT.md: 나만의 봇 만들기
- API.md: API 엔드포인트 문서

---

**버전**: 2.0
**작성일**: 2026-02-03
**작성자**: 무아 & Claude
