# AI Social Bot - 구현 설계 문서

**버전:** 1.0
**작성일:** 2026-02-03
**기반 문서:**
- `AI_Social_Bot_Specification_v2.md` (프로젝트 기획서)
- Planner Agent 아키텍처 설계 출력물 (`velvety-mapping-cook-agent-a0d65f0.md`)

---

## 목차

1. [모듈 의존성 그래프](#1-모듈-의존성-그래프)
2. [레이어 아키텍처](#2-레이어-아키텍처)
3. [핵심 디자인 패턴](#3-핵심-디자인-패턴)
4. [충돌 방지 설계](#4-충돌-방지-설계)
5. [하드코딩 근절 전략](#5-하드코딩-근절-전략)
6. [최적 빌드 순서](#6-최적-빌드-순서)
7. [백엔드 파일 구조](#7-백엔드-파일-구조)
8. [프론트엔드 파일 구조](#8-프론트엔드-파일-구조)
9. [테스트 전략](#9-테스트-전략)
10. [인터페이스 정의](#10-인터페이스-정의)

---

## 1. 모듈 의존성 그래프

### 1.1 계층별 의존성 맵 (Topological Dependency Map)

각 화살표는 "~에 의존한다"를 의미한다. 상위 계층일수록 의존성이 적으며 먼저 구현해야 한다.

**왜 이 구조인가:** 모듈을 Tier 0(무의존)부터 Tier 9(프론트엔드)까지 계층화함으로써 순환 의존을 원천 차단하고, 빌드 순서를 기계적으로 결정할 수 있다. 상위 Tier는 하위 Tier만 참조 가능하며, 이 규칙을 어기는 import는 아키텍처 위반으로 간주한다.

```
TIER 0 - 무의존 (기반 모듈)
========================================
  [config]              순수 데이터 로딩: .env + config.json 파싱
  [exceptions]          커스텀 예외 계층 (프로젝트 내부 import 없음)
  [constants]           Enum, 타입 별칭, 센티넬 값

TIER 1 - TIER 0에만 의존
========================================
  [logging_setup]       구조화된 로거 팩토리
      depends on: config (로그 레벨, 로테이션 설정)

  [models]              모든 도메인 객체의 Pydantic 모델 / dataclass
      depends on: constants (enum)

  [events]              이벤트 버스 + 이벤트 타입 정의
      depends on: models (이벤트 페이로드에 도메인 모델 사용)

TIER 2 - 인프라스트럭처
========================================
  [database]            커넥션 풀, 마이그레이션 러너, 기본 리포지토리
      depends on: config (DB 경로, WAL 설정), logging_setup, exceptions

  [http_client]         공유 aiohttp 세션 팩토리 (재시도/백오프 포함)
      depends on: config (타임아웃, 프록시), logging_setup, exceptions

  [rate_limiter]        플랫폼별 Rate Limit 적용
      depends on: config (플랫폼 Rate Limit), logging_setup, models

  [security_filters]    3단계 콘텐츠 필터링 엔진
      depends on: config (차단 키워드/패턴), logging_setup

  [task_queue]          Rate Limit 작업용 우선순위 비동기 큐
      depends on: rate_limiter, logging_setup, events, models

TIER 3 - 리포지토리 (데이터 접근)
========================================
  [conversation_repo]   conversations 테이블 CRUD
      depends on: database, models

  [activity_repo]       activities 테이블 CRUD
      depends on: database, models

  [collected_info_repo] collected_info 테이블 CRUD
      depends on: database, models

  [notification_repo]   notification_log 테이블 CRUD
      depends on: database, models

  [settings_repo]       settings_history 테이블 CRUD
      depends on: database, models

TIER 4 - 플랫폼 어댑터
========================================
  [platform_base]       어댑터 계약을 정의하는 추상 기본 클래스 (ABC)
      depends on: models, exceptions, rate_limiter, http_client

  [botmadang_adapter]   봇마당 전용 구현체
      depends on: platform_base, config (base_url, api_key), security_filters

  [moltbook_adapter]    Moltbook 전용 구현체
      depends on: platform_base, config (base_url, api_key), security_filters

  [platform_registry]   이름으로 어댑터를 인스턴스화하고 보관하는 팩토리
      depends on: platform_base, botmadang_adapter, moltbook_adapter, config

TIER 5 - 핵심 서비스
========================================
  [llm_service]         Ollama 상호작용: generate, chat, model list, health
      depends on: config (ollama url, model name), http_client, logging_setup, task_queue

  [auth_service]        웹 UI 비밀번호 해싱, 세션 토큰, 로그인 시도
      depends on: config (보안 설정), database (세션용 직접 접근 - repo 미사용)

  [strategy_engine]     행동 의사결정: 무엇을, 언제, 어디에 댓글/게시할지
      depends on: config (행동 설정), models, activity_repo,
                  security_filters, llm_service, events

  [notification_service] 플랫폼 알림 폴링, 응답 디스패치
      depends on: platform_registry, notification_repo, activity_repo,
                  strategy_engine, events, task_queue

  [feed_monitor]        주기적 플랫폼 피드 스캔
      depends on: platform_registry, config (모니터링 주기, 키워드),
                  strategy_engine, activity_repo, events, task_queue

  [translation_service] 한국어 <-> 영어 번역 (Ollama 사용)
      depends on: llm_service, task_queue (LLM 요청 뒤에 큐잉)

  [backup_service]      DB + 설정 스냅샷의 JSON 내보내기/가져오기
      depends on: database, config, all repositories

TIER 6 - 스케줄링 및 오케스트레이션
========================================
  [scheduler]           주기적 작업용 Cron 유사 스케줄러
      depends on: config (active_hours, intervals), feed_monitor,
                  notification_service, logging_setup, events

  [kill_switch]         긴급 정지: 파일 기반 + API 기반
      depends on: scheduler, task_queue, events, config

  [health_monitor]      Ollama, DB, 플랫폼, VRAM 주기적 헬스 체크
      depends on: config, llm_service, database, platform_registry

TIER 7 - 애플리케이션 레이어 (FastAPI)
========================================
  [dependency_injection] 모든 서비스용 FastAPI Depends 프로바이더
      depends on: ALL services, config, database

  [middleware_auth]      인증 미들웨어: 세션 검증, IP 필터링
      depends on: auth_service, config (web_security)

  [middleware_logging]   요청/응답 로깅 미들웨어
      depends on: logging_setup

  [routes_auth]          POST /api/auth/login, POST /api/auth/logout
      depends on: auth_service, dependency_injection

  [routes_chat]          POST /api/chat, GET /api/chat/history
      depends on: llm_service, conversation_repo, dependency_injection

  [routes_platforms]     GET /api/platforms, POST /api/platforms/register
      depends on: platform_registry, dependency_injection

  [routes_activities]    GET /api/activities, 활동 로그 엔드포인트
      depends on: activity_repo, dependency_injection

  [routes_settings]      GET/PUT /api/settings, 설정 CRUD
      depends on: config, settings_repo, dependency_injection

  [routes_notifications] GET /api/notifications
      depends on: notification_repo, dependency_injection

  [routes_info]          GET /api/collected-info, 북마크, 검색
      depends on: collected_info_repo, dependency_injection

  [routes_health]        GET /api/health (인증 불필요)
      depends on: health_monitor

  [routes_emergency]     POST /api/emergency-stop
      depends on: kill_switch, dependency_injection

  [routes_backup]        POST /api/backup/export, POST /api/backup/import
      depends on: backup_service, dependency_injection

  [routes_commands]      POST /api/commands (슬래시 명령: /post, /search 등)
      depends on: platform_registry, strategy_engine, dependency_injection

  [ws_manager]           WebSocket 연결 레지스트리 + 브로드캐스트
      depends on: events, auth_service

  [ws_chat]              실시간 채팅용 WebSocket 엔드포인트
      depends on: ws_manager, llm_service, conversation_repo

  [ws_status]            실시간 상태 업데이트용 WebSocket 엔드포인트
      depends on: ws_manager, events, health_monitor

  [ws_audio]             오디오 스트리밍용 WebSocket 엔드포인트 (음성)
      depends on: ws_manager, voice_service (선택)

  [fastapi_app]          앱 팩토리: 라우트, 미들웨어, startup/shutdown 마운트
      depends on: ALL routes, ALL middleware, ws_manager, scheduler,
                  dependency_injection, database (생명주기), config

TIER 8 - 음성 (선택 사항)
========================================
  [voice_service]        Wake Word 감지 + Whisper STT 오케스트레이션
      depends on: config (음성 설정), events, logging_setup

  [wake_word_engine]     openWakeWord / Porcupine 래퍼
      depends on: config (wake_words, 엔진 선택)

  [whisper_engine]       Whisper 모델 로드/언로드/변환
      depends on: config (stt_model, language), health_monitor (VRAM 체크)

TIER 9 - 프론트엔드 (별도 빌드)
========================================
  [react_app]            React + Vite SPA
      depends on: 백엔드 API 계약 (OpenAPI 스펙)
      internal deps: components -> hooks -> services -> stores -> types
```

### 1.2 크리티컬 의존성 체인

시스템에서 가장 긴 의존 경로들이다. 이 체인에 속한 모듈에 버그나 지연이 발생하면 하류의 모든 모듈에 영향을 준다.

**왜 이것이 중요한가:** 크리티컬 체인을 식별하면 개발 우선순위와 코드 리뷰 집중 영역을 결정할 수 있다. 체인 A의 `config`에 문제가 생기면 `fastapi_app`까지 모든 것이 멈춘다.

```
Chain A (핵심 데이터 흐름):
  config -> database -> activity_repo -> strategy_engine -> feed_monitor -> scheduler -> fastapi_app

Chain B (플랫폼 통신):
  config -> http_client -> platform_base -> botmadang_adapter -> platform_registry -> notification_service -> scheduler

Chain C (LLM 파이프라인):
  config -> http_client -> llm_service -> strategy_engine -> feed_monitor

Chain D (인증 흐름):
  config -> auth_service -> middleware_auth -> fastapi_app
```

### 1.3 순환 의존 방지 규칙

| 위험 요소 | 관련 모듈 | 방지 방법 |
|-----------|----------|----------|
| Strategy가 LLM을 필요로 하고, LLM 큐가 Strategy 컨텍스트를 필요로 함 | `strategy_engine` <-> `llm_service` | Strategy는 단방향 인터페이스를 통해 LLM을 호출. LLM 서비스는 Strategy에 대한 지식이 전혀 없음. |
| 서비스가 이벤트를 발행하고, 다른 서비스가 소비 | `feed_monitor` <-> `notification_service` | 이벤트 버스로 디커플링. 양쪽 모두 서로를 import하지 않음. 양쪽 모두 `events`만 import. |
| Config 리로드가 서비스 재초기화를 트리거 | `config` <-> services | Config가 observable을 노출. 서비스가 구독. Config는 절대 서비스를 import하지 않음. |
| 리포지토리가 모델을 필요로 하고, 모델이 리포지토리 근처에 정의됨 | `models` <-> `*_repo` | 모델은 별도의 순수 모듈에 존재. 리포지토리가 모델을 import하며, 역방향은 절대 없음. |

---

## 2. 레이어 아키텍처

### 2.1 레이어 다이어그램

**왜 5레이어인가:** 각 레이어는 명확한 단일 책임을 가진다. Presentation은 사용자 인터랙션, Application은 HTTP 라우팅, Service는 비즈니스 로직, Domain은 순수 데이터 구조, Infrastructure는 I/O를 담당한다. 이 분리로 테스트 용이성, 교체 가능성, 팀 병렬 개발이 보장된다.

```
+------------------------------------------------------------------+
|                    PRESENTATION LAYER                              |
|  React SPA: components, hooks, stores, WebSocket clients          |
|  Application Layer와 HTTP/REST + WebSocket으로만 통신              |
+------------------------------------------------------------------+
                              |
                    HTTP / WebSocket
                              |
+------------------------------------------------------------------+
|                    APPLICATION LAYER                               |
|  FastAPI routes, middleware, WebSocket handlers                    |
|  Dependency injection providers                                   |
|  요청 검증 (Pydantic request models)                              |
|  응답 직렬화 (Pydantic response models)                           |
|  비즈니스 로직 없음 - 서비스 호출만 오케스트레이션                    |
+------------------------------------------------------------------+
                              |
                     메서드 호출
                              |
+------------------------------------------------------------------+
|                    SERVICE LAYER                                   |
|  LLM Service, Strategy Engine, Feed Monitor, Notification Service |
|  Translation Service, Auth Service, Backup Service                |
|  Platform Registry, Scheduler, Health Monitor, Kill Switch        |
|  모든 비즈니스 로직이 여기 존재                                     |
|  서비스가 리포지토리와 어댑터를 조율                                 |
+------------------------------------------------------------------+
                              |
              메서드 호출      |    메서드 호출
              (하향 전용)      |    (하향 전용)
         +--------------------+--------------------+
         |                                         |
+------------------+                    +------------------+
|   DOMAIN LAYER   |                    | ADAPTER LAYER    |
|  Models (Pydantic)|                    | PlatformBase ABC |
|  비즈니스 규칙    |                    | BotmadangAdapter |
|  검증 로직        |                    | MoltbookAdapter  |
|  이벤트 타입      |                    | Ollama client    |
+------------------+                    +------------------+
         |                                         |
         |                                         |
+------------------------------------------------------------------+
|                    INFRASTRUCTURE LAYER                            |
|  Config loader, Database (SQLite + aiosqlite), HTTP client        |
|  Rate Limiter, Task Queue, Security Filters, Logging              |
|  Exception hierarchy, Constants/Enums                             |
+------------------------------------------------------------------+
```

### 2.2 레이어 규칙 (엄격 적용)

| 규칙 | 설명 |
|------|------|
| **하향 전용 (Downward-only)** | 레이어는 자신보다 아래 레이어에서만 import 가능. 상향 import 절대 불가. |
| **Presentation 격리** | React 앱은 Python import가 전혀 없음. HTTP/WS로만 통신. |
| **Application은 얇게** | 라우트에 비즈니스 로직 없음. 입력 검증 -> 서비스 호출 -> 출력 반환만 수행. |
| **Service는 두텁게** | 모든 비즈니스 결정이 여기서 발생. 서비스는 여러 리포지토리와 어댑터를 호출 가능. |
| **Domain은 순수하게** | 모델과 비즈니스 규칙에 I/O 없음. 데이터베이스, HTTP, 파일시스템 접근 금지. |
| **Adapter는 교체 가능하게** | 각 어댑터가 ABC를 구현. 봇마당을 새 플랫폼으로 교체 = 새 파일 하나 작성. |
| **Infrastructure는 범용적으로** | 인프라에서 "게시글"이나 "댓글"을 알지 못함. "연결", "쿼리", "HTTP 요청"만 앎. |

### 2.3 레이어-모듈 매핑

**Infrastructure Layer:**
```
app/core/config.py              - Config 로딩 및 검증
app/core/exceptions.py          - 예외 계층
app/core/constants.py           - Enum, 타입 별칭
app/core/logging.py             - 로거 팩토리
app/core/events.py              - 이벤트 버스
app/core/database.py            - SQLite 연결 관리
app/core/http_client.py         - aiohttp 세션 팩토리
app/core/rate_limiter.py        - Rate Limit 적용
app/core/task_queue.py          - 비동기 우선순위 큐
app/core/security.py            - 콘텐츠 필터링 엔진
```

**Domain Layer:**
```
app/models/conversation.py      - Conversation 모델
app/models/activity.py          - Activity 모델
app/models/notification.py      - Notification 모델
app/models/collected_info.py    - CollectedInfo 모델
app/models/settings.py          - Settings 스냅샷 모델
app/models/platform.py          - 플랫폼 관련 DTO (post, comment, vote)
app/models/events.py            - 이벤트 페이로드 모델
app/models/auth.py              - 인증 관련 모델 (session, login)
app/models/health.py            - 헬스 체크 응답 모델
```

**Adapter Layer (리포지토리 + 플랫폼 어댑터):**
```
app/repositories/base.py        - 공통 CRUD를 가진 BaseRepository
app/repositories/conversation.py
app/repositories/activity.py
app/repositories/notification.py
app/repositories/collected_info.py
app/repositories/settings.py

app/platforms/base.py            - PlatformAdapter ABC
app/platforms/botmadang.py       - 봇마당 구현체
app/platforms/moltbook.py        - Moltbook 구현체
app/platforms/registry.py        - 플랫폼 팩토리/레지스트리
```

**Service Layer:**
```
app/services/llm.py              - Ollama LLM 상호작용
app/services/auth.py             - 웹 UI 인증
app/services/strategy.py         - 행동 의사결정 엔진
app/services/notifications.py    - 알림 폴링 + 대응
app/services/feed_monitor.py     - 피드 스캔
app/services/translation.py      - LLM 기반 번역
app/services/backup.py           - 내보내기/가져오기
app/services/scheduler.py        - 주기적 작업 스케줄러
app/services/kill_switch.py      - 긴급 정지
app/services/health.py           - 헬스 모니터링
app/services/voice.py            - 음성 오케스트레이션 (선택)
```

**Application Layer:**
```
app/api/dependencies.py          - FastAPI Depends 프로바이더
app/api/middleware/auth.py        - 인증 미들웨어
app/api/middleware/logging.py     - 요청 로깅 미들웨어
app/api/routes/auth.py
app/api/routes/chat.py
app/api/routes/platforms.py
app/api/routes/activities.py
app/api/routes/settings.py
app/api/routes/notifications.py
app/api/routes/info.py
app/api/routes/health.py
app/api/routes/emergency.py
app/api/routes/backup.py
app/api/routes/commands.py
app/api/routes/setup_wizard.py
app/api/websocket/manager.py
app/api/websocket/chat.py
app/api/websocket/status.py
app/api/websocket/audio.py
app/main.py                      - 앱 팩토리
```

---

## 3. 핵심 디자인 패턴

### 3.1 Repository 패턴 (데이터베이스 접근)

**왜 이 패턴인가:** SQLite 세부사항을 서비스로부터 추상화한다. 인메모리 DB 또는 Mock으로 테스트를 가능하게 한다. SQL이 존재하는 단일 지점을 제공하여 쿼리 변경 시 영향 범위를 최소화한다.

**구조:**
```
BaseRepository
  - 데이터베이스 커넥션 풀에 대한 참조 보유
  - 제공: execute(), fetch_one(), fetch_all(), execute_returning_id()
  - busy_timeout 재시도를 내부 처리 (3회 시도)

ConversationRepository(BaseRepository)
  - add(role, content, platform) -> Conversation
  - get_history(limit, offset, platform_filter) -> list[Conversation]
  - get_by_id(id) -> Conversation | None

ActivityRepository(BaseRepository)
  - add(activity: ActivityCreate) -> Activity
  - get_by_platform_post(platform, post_id) -> list[Activity]
  - has_responded_to(platform, post_id) -> bool  # 중복 방지에 핵심
  - get_daily_counts(platform, date) -> DailyCounts
  - get_by_status(status, limit) -> list[Activity]
  - update_status(id, status, error_message) -> None
  - get_timeline(start, end, platform_filter, type_filter) -> list[Activity]

NotificationRepository(BaseRepository)
  - add(notification: NotificationCreate) -> NotificationLog
  - get_unprocessed(platform) -> list[NotificationLog]
  - mark_responded(id, response_activity_id) -> None
  - get_last_check_time(platform) -> datetime | None

CollectedInfoRepository(BaseRepository)
  - add(info: CollectedInfoCreate) -> CollectedInfo
  - search(query, category, bookmarked_only) -> list[CollectedInfo]
  - toggle_bookmark(id) -> bool
  - get_categories() -> list[str]

SettingsRepository(BaseRepository)
  - save_snapshot(config_json: str) -> None
  - get_latest() -> str | None
  - get_history(limit) -> list[SettingsSnapshot]
```

**핵심 규칙:** 리포지토리는 도메인 모델 인스턴스를 반환한다. 절대 raw dict나 Row 객체를 반환하지 않는다.

### 3.2 Adapter 패턴 (플랫폼 통합)

**왜 이 패턴인가:** 두 플랫폼(봇마당, Moltbook)이 서로 다른 API, 인증 흐름, Rate Limit, 기능을 가진다. 내일 세 번째 플랫폼이 추가될 수 있다. 시스템은 어떤 플랫폼과 통신하는지 신경 쓰지 않아야 한다.

**계약 (PlatformAdapter ABC):**

모든 메서드는 도메인 레이어에 정의된 표준화된 결과 타입을 반환한다. 플랫폼별 필드는 각 어댑터 내부에서 매핑된다.

```
PlatformAdapter (ABC)
  Properties:
    - platform_name: str
    - is_authenticated: bool
    - rate_limiter: RateLimiter (주입됨, 플랫폼별 인스턴스)

  Auth:
    - authenticate() -> AuthResult
    - validate_credentials() -> bool

  Read:
    - get_posts(sort, limit, community_filter) -> list[PlatformPost]
    - get_post_detail(post_id) -> PlatformPost
    - get_comments(post_id) -> list[PlatformComment]
    - get_notifications(since, unread_only) -> list[PlatformNotification]
    - get_communities() -> list[PlatformCommunity]
    - search(query, semantic) -> list[PlatformPost]  # semantic=True는 Moltbook만

  Write:
    - create_post(title, content, community) -> PlatformPostResult
    - create_comment(post_id, content, parent_comment_id) -> PlatformCommentResult
    - upvote(post_id) -> bool
    - downvote(post_id) -> bool
    - mark_notifications_read(notification_ids) -> bool

  Platform-specific (선택, 기본적으로 NotImplementedError 발생):
    - follow(agent_id) -> bool            # Moltbook 전용
    - unfollow(agent_id) -> bool          # Moltbook 전용
    - register_agent(name, desc) -> RegistrationResult  # 봇마당 전용

  Meta:
    - get_rate_limit_config() -> RateLimitConfig
    - get_capabilities() -> set[PlatformCapability]
```

**Capability enum** - 호출자가 플랫폼이 무엇을 지원하는지 추측하는 것을 방지:
```python
class PlatformCapability(Enum):
    SEMANTIC_SEARCH = "semantic_search"
    FOLLOW = "follow"
    NESTED_COMMENTS = "nested_comments"
    NOTIFICATIONS = "notifications"
    AGENT_REGISTRATION = "agent_registration"
    DOWNVOTE = "downvote"
```

### 3.3 Strategy 패턴 (행동 엔진)

**왜 이 패턴인가:** 봇의 의사결정 로직은 가장 복잡하고 변경 가능성이 가장 높다. 새로운 전략(예: "공격적 학습자", "조용한 관찰자")이 플러그인 가능해야 한다. Strategy 패턴은 알고리즘을 캡슐화하여 런타임에 교체할 수 있게 한다.

**구조:**
```
BehaviorStrategy (ABC)
  - should_comment(post: PlatformPost, context: StrategyContext) -> CommentDecision
  - should_post(context: StrategyContext) -> PostDecision
  - should_upvote(post: PlatformPost, context: StrategyContext) -> bool
  - select_community(content: str, platform_communities: list) -> str
  - prioritize_posts(posts: list[PlatformPost], context: StrategyContext) -> list[PlatformPost]

StrategyContext (dataclass)
  - daily_counts: DailyCounts
  - daily_limits: DailyLimits
  - interest_keywords: list[str]
  - recent_activities: list[Activity]
  - current_time: datetime
  - active_hours: ActiveHoursConfig

CommentDecision (dataclass)
  - should_comment: bool
  - reason: str                    # 로깅용
  - priority: int                  # 큐 우선순위
  - delay_seconds: int             # 지터

DefaultBehaviorStrategy(BehaviorStrategy)
  - 기획서 섹션 5.2의 댓글 의사결정 트리를 구현
  - 설정값으로 임계값 설정
  - 설정 범위 내 지터 추가
```

전략 엔진(서비스 레이어)은 이를 감싼다:
```
StrategyEngine
  - __init__(strategy: BehaviorStrategy, llm: LLMService, config: Config)
  - evaluate_post(post, platform) -> CommentDecision
  - generate_comment(post, platform) -> QualityCheckedComment
  - generate_reply(notification, context) -> QualityCheckedComment
  - generate_post(topic, platform) -> QualityCheckedPost
  - check_quality(content, platform, original) -> QualityResult
```

### 3.4 Observer / Event 패턴 (디커플링)

**왜 이 패턴인가:** 서비스들은 서로를 import하지 않으면서 다른 곳에서 발생하는 일에 반응해야 한다. 스케줄러가 WebSocket 매니저를 import해서는 안 되고, 피드 모니터가 활동 로거를 import해서는 안 된다. 이벤트 버스가 이 문제를 해결한다.

**EventBus 설계:**
```
EventBus (싱글톤 유사, DI를 통해 주입)
  - subscribe(event_type: type[Event], handler: Callable) -> None
  - unsubscribe(event_type: type[Event], handler: Callable) -> None
  - publish(event: Event) -> None  # async, 논블로킹 fan-out

이벤트는 타입이 지정된 dataclass:
  - NewPostDiscoveredEvent(platform, post: PlatformPost)
  - CommentPostedEvent(platform, activity: Activity)
  - PostCreatedEvent(platform, activity: Activity)
  - NotificationReceivedEvent(platform, notification: PlatformNotification)
  - ConfigChangedEvent(section: str, old_value, new_value)
  - PlatformErrorEvent(platform, error: PlatformError)
  - EmergencyStopEvent(source: str)  # "file" 또는 "api"
  - HealthCheckEvent(results: HealthCheckResult)
  - LLMResponseEvent(request_id, response_text)
  - VoiceCommandEvent(transcript: str)
  - ApprovalRequestedEvent(activity: Activity)
  - ApprovalResolvedEvent(activity_id, approved: bool)
```

**구독 맵 (누가 무엇을 수신하는가):**

| 이벤트 | 구독자 |
|-------|-------|
| `NewPostDiscoveredEvent` | StrategyEngine (평가), CollectedInfoRepo (관련 시 저장) |
| `CommentPostedEvent` | ActivityRepo (이미 저장됨), WSManager (UI에 브로드캐스트) |
| `NotificationReceivedEvent` | NotificationService (응답 디스패치), WSManager (브로드캐스트) |
| `ConfigChangedEvent` | RateLimiter (재초기화), Scheduler (재스케줄), PlatformRegistry (재설정) |
| `EmergencyStopEvent` | Scheduler (전체 중지), TaskQueue (드레인), WSManager (클라이언트 알림) |
| `PlatformErrorEvent` | HealthMonitor (추적), WSManager (UI에 에러 표시) |
| `ApprovalRequestedEvent` | WSManager (프론트엔드에 사용자 결정 요청 전송) |

### 3.5 Queue 패턴 (Rate-Limited 작업)

**왜 이 패턴인가:** 여러 소스(피드 모니터, 알림 응답기, 수동 명령, 전략 엔진)가 모두 게시/댓글을 원한다. 플랫폼별 Rate Limit을 적용하는 단일 초크 포인트를 통과해야 한다.

**설계:**
```
TaskQueue
  - 플랫폼 키 기반 내부 큐: dict[str, asyncio.PriorityQueue]
  - 각 큐는 전용 소비자 코루틴 보유
  - 소비자는 실행 전 rate_limiter 확인
  - Rate Limit 시 쿨다운 만료까지 sleep (busy-wait 아님)

QueuedTask (dataclass)
  - priority: int              # 낮을수록 높은 우선순위. Notifications = 1, scheduled = 5
  - created_at: datetime
  - platform: str
  - action: Callable[..., Awaitable]  # 실제 API 호출
  - args: tuple
  - kwargs: dict
  - retry_count: int = 0
  - max_retries: int = 3
  - callback: Callable | None  # 성공 후 결과와 함께 호출

흐름:
  1. 서비스가 QueuedTask 생성, TaskQueue에 제출
  2. TaskQueue가 플랫폼별 우선순위 큐에 배치
  3. 소비자 코루틴이 최고 우선순위 작업 선택
  4. rate_limiter.can_execute(platform, action_type) 확인
  5. 가능하면: 실행, 콜백 호출, 성공 로그
  6. 불가하면: 대기 시간 계산, asyncio.sleep(wait_time), 재시도
  7. 실패 시: retry_count 증가, 백오프 지연과 함께 재큐잉
  8. 최대 재시도 시: 에러 로그, 활동을 'failed'로 표시, PlatformErrorEvent 발행
```

**LLM 큐 (특수 케이스):**

Ollama는 한 번에 하나의 요청만 처리한다. LLM 서비스는 접근을 직렬화하기 위해 자체 asyncio.Lock을 유지한다. LLM 요청에는 Rate Limit이 없고 직렬화만 필요하므로 전체 큐보다 단순하다.

```
LLMService
  - _lock: asyncio.Lock
  - async generate(prompt, system, stream) -> str | AsyncIterator[str]
      async with self._lock:
          return await self._call_ollama(...)
```

**실용적 접근:** LLM 요청은 보통 수 초가 걸리고, 시스템이 분당 약 1개 댓글을 생성하므로 경합이 낮다. 단순 asyncio.Lock으로 충분하다. 채팅 지연이 문제가 되면 나중에 우선순위 잠금을 도입할 수 있다.

**스트리밍 고려사항:** 채팅(사용자 대면)에는 스트리밍을 사용하여 사용자가 토큰을 즉시 볼 수 있게 한다. 백그라운드 작업(댓글 생성)에는 논스트리밍을 사용하여 큐 관리를 단순화한다. 잠금은 두 경우 모두 전체 생성 기간 동안 유지된다.

### 3.6 Middleware 패턴 (인증 / 보안)

**왜 이 패턴인가:** 횡단 관심사(인증, IP 필터링, 요청 로깅, CORS)를 라우트 핸들러를 오염시키지 않고 균일하게 적용해야 한다.

**미들웨어 스택 (순서 중요, 첫 번째 = 가장 바깥):**
```
1. CORSMiddleware          - 표준 FastAPI CORS (프론트엔드 origin)
2. RequestLoggingMiddleware - 모든 요청/응답을 api.log에 로깅
3. IPFilterMiddleware       - allowed_ips / allow_all_local 확인
4. AuthMiddleware           - 쿠키/헤더의 세션 토큰 검증
                             면제 경로: /api/health, /api/auth/login, /static/*
5. [FastAPI 라우트 실행]
```

### 3.7 Dependency Injection (FastAPI Depends)

**왜 이 패턴인가:** FastAPI의 Depends 시스템은 서비스를 라우트에 연결하는 자연스러운 방법이다. 자동 생명주기 관리와 테스트 용이성을 제공한다.

**프로바이더 계층:**
```python
# Tier 0: Config (캐시됨, 한 번 생성)
def get_config() -> Config:
    return Config.get_instance()

# Tier 1: Database (앱 생명주기 범위)
async def get_db(config: Config = Depends(get_config)) -> Database:
    return Database.get_instance()

# Tier 2: Repositories (요청별, 생성 비용 저렴)
async def get_activity_repo(db: Database = Depends(get_db)) -> ActivityRepository:
    return ActivityRepository(db)

# Tier 3: Services (앱 생명주기 범위 싱글톤, app.state에서 조회)
def get_llm_service(request: Request) -> LLMService:
    return request.app.state.llm_service

def get_strategy_engine(request: Request) -> StrategyEngine:
    return request.app.state.strategy_engine

def get_platform_registry(request: Request) -> PlatformRegistry:
    return request.app.state.platform_registry

# Tier 4: Auth (요청별, 미들웨어 결과에서)
def get_current_session(request: Request) -> Session:
    session = request.state.session  # AuthMiddleware가 설정
    if not session:
        raise HTTPException(401)
    return session
```

**Startup / Shutdown 생명주기:**
```python
@asynccontextmanager
async def lifespan(app: FastAPI):
    # STARTUP
    config = Config.load()
    db = await Database.initialize(config)
    await db.run_migrations()

    event_bus = EventBus()
    http_client = await HttpClientFactory.create(config)
    rate_limiters = RateLimiterFactory.create_all(config)
    task_queue = TaskQueue(rate_limiters, event_bus)

    platform_registry = PlatformRegistry(config, http_client, rate_limiters)
    llm_service = LLMService(config, http_client)
    auth_service = AuthService(config, db)
    strategy = DefaultBehaviorStrategy(config)
    strategy_engine = StrategyEngine(strategy, llm_service, config)
    notification_service = NotificationService(platform_registry, ...)
    feed_monitor = FeedMonitor(platform_registry, strategy_engine, ...)
    scheduler = Scheduler(config, feed_monitor, notification_service, ...)
    health_monitor = HealthMonitor(config, llm_service, db, platform_registry)
    kill_switch = KillSwitch(scheduler, task_queue, event_bus, config)
    ws_manager = WebSocketManager(event_bus, auth_service)

    # app.state에 저장하여 DI 접근 가능
    app.state.config = config
    app.state.db = db
    app.state.event_bus = event_bus
    app.state.llm_service = llm_service
    # ... 기타

    await scheduler.start()
    await task_queue.start()
    await health_monitor.start()

    yield  # 앱 실행

    # SHUTDOWN
    await kill_switch.graceful_shutdown()
    await scheduler.stop()
    await task_queue.drain_and_stop()
    await http_client.close()
    await db.close()
```

---

## 4. 충돌 방지 설계

### 4.1 SQLite 비동기 FastAPI 환경의 쓰기 경합

**문제:** SQLite는 한 번에 하나의 쓰기만 허용한다. aiosqlite를 사용하는 비동기 FastAPI 앱에서 여러 코루틴이 동시 쓰기를 시도할 수 있다.

**해결책: asyncio.Lock을 통한 쓰기 직렬화 + WAL 모드**

**왜 이 방식인가:** WAL(Write-Ahead Logging) 모드는 읽기-쓰기 경합을 제거하고(읽기가 쓰기를 블로킹하지 않음), asyncio.Lock은 Python 프로세스 내 쓰기를 직렬화한다. 이 조합은 OS 수준 경합 없이 비동기 환경에서 안전한 동시성을 보장한다.

```
Database class:
  - _write_lock: asyncio.Lock (Database 인스턴스당 하나)
  - 연결 시 WAL 모드 활성화 (PRAGMA journal_mode=WAL)
  - 연결 시 busy_timeout=5000 설정

  읽기: 잠금 불필요. WAL 모드는 쓰기 중에도 동시 읽기 허용.
        여러 코루틴이 동시에 읽기 가능.

  쓰기: 모든 쓰기는 단일 메서드를 통과:
    async def execute_write(self, sql, params) -> Any:
        async with self._write_lock:
            async with self._pool.acquire() as conn:
                result = await conn.execute(sql, params)
                await conn.commit()
                return result

  배치 쓰기: 여러 문장에 걸친 원자성이 필요한 작업:
    async def execute_write_transaction(self, operations: list[tuple[str, tuple]]) -> None:
        async with self._write_lock:
            async with self._pool.acquire() as conn:
                for sql, params in operations:
                    await conn.execute(sql, params)
                await conn.commit()
```

**작동 원리:**
- WAL 모드가 읽기-쓰기 경합을 제거 (읽기가 쓰기를 블로킹하지 않고, 쓰기가 읽기를 블로킹하지 않음)
- asyncio.Lock이 Python 프로세스 내 쓰기를 직렬화 (OS 수준 경합 없음)
- busy_timeout은 외부 도구(예: DB 브라우저)가 잠금을 잡는 엣지 케이스를 처리
- 잠금이 async이므로 대기 중인 코루틴은 이벤트 루프에 양보 (스레드 블로킹 없음)

**커넥션 풀 사이징:** 1개의 쓰기 전용 연결 + N개의 읽기 전용 연결(N = 4가 합리적). aiosqlite는 네이티브 풀링을 지원하지 않으므로 간단한 래퍼를 구현:
```
WriterConnection: 단일 연결, _write_lock으로 보호
ReaderPool: N개 연결 목록, 라운드로빈 또는 asyncio.Semaphore로 분배
```

### 4.2 비동기 작업 간 Rate Limiter 공유 상태

**문제:** 여러 코루틴이 Rate Limit 상태를 동시에 확인하고 업데이트한다. 전형적인 TOCTOU(time-of-check/time-of-use) 레이스 컨디션.

**해결책: Limiter별 asyncio.Lock을 통한 원자적 Check-and-Reserve**

**왜 이 방식인가:** 플랫폼별 독립 잠금을 사용하면 봇마당의 Rate Limit이 Moltbook에 영향을 주지 않으면서도 각 플랫폼 내에서는 원자적 상태 변경을 보장한다.

```
PlatformRateLimiter:
  - _lock: asyncio.Lock
  - _last_post_time: float
  - _last_comment_time: float
  - _api_calls_window: deque[float]  # 타임스탬프의 슬라이딩 윈도우
  - _daily_comment_count: int
  - _daily_reset_date: date

  async def acquire(self, action_type: ActionType) -> AcquireResult:
      """원자적 check-and-reserve. 결과를 즉시 반환."""
      async with self._lock:
          now = time.monotonic()
          # ... 쿨다운, 카운터 확인 ...
          if can_proceed:
              self._update_state(action_type, now)
              return AcquireResult(allowed=True, wait_seconds=0)
          else:
              return AcquireResult(allowed=False, wait_seconds=remaining_cooldown)

  async def wait_and_acquire(self, action_type: ActionType) -> None:
      """작업이 허용될 때까지 블로킹. 큐 소비자용."""
      while True:
          result = await self.acquire(action_type)
          if result.allowed:
              return
          await asyncio.sleep(result.wait_seconds)
```

**핵심 설계 결정:**
- 플랫폼 Limiter별 하나의 잠금 (전역 잠금 아님). 봇마당 Rate Limit은 Moltbook과 독립적.
- `acquire()`는 논블로킹 (즉시 반환). 호출자가 대기할지 재큐잉할지 결정.
- `wait_and_acquire()`는 허용될 때까지 루프하는 큐 소비자용.
- 일일 카운터는 타이머가 아닌 날짜 비교로 리셋.

### 4.3 재시작 없는 Config 핫 리로드

**문제:** 사용자가 웹 UI를 통해 설정을 변경한다. 일부 설정(행동 임계값, 키워드, 스케줄)은 즉시 적용되어야 하고, 다른 설정(데이터베이스 경로, 서버 포트)은 재시작이 필요하다.

**해결책: Observable을 가진 2단계 Config**

**왜 이 방식인가:** 모든 설정을 재시작 없이 반영하면 위험하고(포트 변경 등), 모든 설정에 재시작을 요구하면 UX가 나빠진다. 2단계 분류로 안전성과 편의성을 모두 확보한다.

```
Config:
  HOT_RELOADABLE 섹션:
    - behavior.*          (모니터링 주기, 키워드, 한도, 지터)
    - security.*          (차단 키워드, 패턴)
    - voice.*             (wake words, STT 모델)
    - web_security.*      (세션 타임아웃, 허용 IP)
    - ui.*                (테마, 언어)
    - platforms.*.enabled (플랫폼 활성화/비활성화)

  RESTART_REQUIRED 섹션:
    - server.port
    - server.host
    - database.path
    - platforms.*.base_url

  구현:
    class Config:
        _data: dict                 # 현재 설정
        _observers: dict[str, list[Callable]]  # 섹션 -> 핸들러
        _lock: asyncio.Lock         # 리로드 중 _data 보호

        async def update_section(self, section: str, new_value: Any) -> UpdateResult:
            async with self._lock:
                old_value = self._data.get(section)
                if section in RESTART_REQUIRED_SECTIONS:
                    # 파일에 저장하되 "재시작 대기" 표시
                    self._save_to_file()
                    return UpdateResult(applied=False, needs_restart=True)
                else:
                    self._data[section] = new_value
                    self._save_to_file()
                    await self._notify_observers(section, old_value, new_value)
                    return UpdateResult(applied=True, needs_restart=False)

        def subscribe(self, section: str, handler: Callable) -> None:
            self._observers.setdefault(section, []).append(handler)
```

**구독 관계:**

| Config 섹션 | 구독자 | 변경 시 동작 |
|-------------|-------|------------|
| `behavior.monitoring_interval_minutes` | Scheduler | 피드 모니터 주기 재설정 |
| `behavior.interest_keywords` | StrategyEngine | 키워드 집합 갱신 |
| `behavior.daily_limits` | StrategyEngine | 한도 임계값 갱신 |
| `behavior.active_hours` | Scheduler | 활동 시간 윈도우 갱신 |
| `security.blocked_keywords` | SecurityFilter | 필터 패턴 재컴파일 |
| `platforms.*.enabled` | PlatformRegistry | 어댑터 활성화/비활성화 |
| `voice.enabled` | VoiceService | 음성 파이프라인 시작/중지 |

### 4.4 WebSocket 상태 동기화

**문제:** 여러 WebSocket 클라이언트가 연결될 수 있다(여러 브라우저 탭). 각각이 일관된 상태를 받아야 한다. 끊긴 후 재연결하는 클라이언트는 따라잡아야 한다.

**해결책: 연결 레지스트리 + 이벤트 기반 브로드캐스트 + 연결 시 상태 스냅샷**

**왜 이 방식인가:** 이벤트 기반 브로드캐스트는 실시간성을 보장하고, 연결 시 상태 스냅샷은 재연결 시 전체 상태를 즉시 동기화하여 중간 이벤트를 놓쳐도 문제없게 한다.

```
WebSocketManager:
  - _connections: dict[str, WebSocketConnection]  # connection_id -> connection
  - _lock: asyncio.Lock   # _connections dict 보호

  async def connect(self, websocket, session) -> str:
      connection_id = uuid4().hex
      async with self._lock:
          self._connections[connection_id] = WebSocketConnection(
              websocket=websocket,
              session=session,
              connected_at=datetime.utcnow()
          )
      # 연결 직후 현재 상태 스냅샷 전송
      await self._send_state_snapshot(websocket)
      return connection_id

  async def disconnect(self, connection_id) -> None:
      async with self._lock:
          self._connections.pop(connection_id, None)

  async def broadcast(self, event_type: str, data: dict) -> None:
      """모든 연결된 클라이언트에 전송. 이벤트 핸들러에서 호출."""
      async with self._lock:
          connections = list(self._connections.values())
      # I/O 전에 잠금 해제
      dead_connections = []
      for conn in connections:
          try:
              await conn.websocket.send_json({"type": event_type, "data": data})
          except WebSocketDisconnect:
              dead_connections.append(conn.id)
      # 죽은 연결 정리
      if dead_connections:
          async with self._lock:
              for cid in dead_connections:
                  self._connections.pop(cid, None)

  async def _send_state_snapshot(self, websocket) -> None:
      """재연결 시 전체 현재 상태 전송."""
      snapshot = {
          "type": "state_sync",
          "data": {
              "bot_status": health_monitor.get_current_status(),
              "platforms": platform_registry.get_status_summary(),
              "scheduler_state": scheduler.get_state(),
              "pending_approvals": task_queue.get_pending_approvals(),
              "recent_activities": activity_repo.get_recent(limit=20)
          }
      }
      await websocket.send_json(snapshot)
```

**프론트엔드 재연결 프로토콜:**
```
1. WebSocket 종료 (의도적 또는 에러)
2. 프론트엔드가 "재연결 중" 상태 진입 (인디케이터 표시)
3. 지수 백오프: 1초, 2초, 4초, 8초, 16초, 최대 30초
4. 재연결 시: 서버가 state_sync 메시지 전송
5. 프론트엔드가 전체 로컬 상태를 스냅샷으로 교체
6. 프론트엔드가 "연결됨" 상태 진입
```

### 4.5 다중 플랫폼 API 동시 호출

**문제:** 피드 모니터가 Moltbook과 봇마당을 동시에 폴링한다. 둘 다 동시에 큐에 들어가는 작업을 생성할 수 있다. 어댑터 인스턴스는 비동기 사용에 대해 스레드 안전해야 한다.

**해결책: 플랫폼별 격리 + 공유 없는 어댑터**

**왜 이 방식인가:** Shared-Nothing 원칙은 잠금 없이 동시성을 달성한다. 각 어댑터가 독립적 상태를 가지므로 한 플랫폼의 문제가 다른 플랫폼에 전파되지 않는다.

```
설계 원칙:
  1. 각 PlatformAdapter 인스턴스는 하나의 플랫폼에만 사용
  2. 어댑터 간 가변 상태 공유 없음
  3. 각 어댑터가 자체 보유:
     - HTTP 세션 (또는 본질적으로 동시성 안전한 공유 세션)
     - Rate Limiter 인스턴스
     - 인증 상태
  4. TaskQueue는 플랫폼별 내부 큐 보유 (3.5 참조)
  5. 피드 모니터가 플랫폼 폴링을 동시에 실행:

     async def poll_all_platforms(self):
         tasks = []
         for platform in self.registry.get_enabled_platforms():
             tasks.append(self._poll_platform(platform))
         results = await asyncio.gather(*tasks, return_exceptions=True)
         for platform, result in zip(platforms, results):
             if isinstance(result, Exception):
                 self.event_bus.publish(PlatformErrorEvent(platform.name, result))

  6. aiohttp.ClientSession은 동시 사용에 안전 (설계상)
     - HttpClientFactory에서 하나의 세션 생성, 어댑터 간 공유
     - 각 어댑터가 자체 요청 생성; aiohttp가 내부적으로 동시성 처리
```

### 4.6 LLM 요청 큐잉 (Ollama 단일 요청 제한)

**문제:** Ollama는 한 번에 하나의 생성만 처리한다. 여러 서비스(댓글용 전략 엔진, 번역 서비스, 직접 채팅)가 모두 LLM 접근을 필요로 한다.

**해결책: 채팅 우선 바이패스를 가진 asyncio.Lock**

**왜 이 방식인가:** 단순 asyncio.Lock은 경합이 낮은 현재 환경에 충분하며, 복잡한 우선순위 큐보다 유지보수가 쉽다. 채팅 지연이 문제가 되면 PriorityLock으로 업그레이드할 수 있다.

```
LLMService:
  _lock: asyncio.Lock
  _current_request_id: str | None = None

  async def generate(self, prompt, system, stream=False, priority="normal") -> ...:
      request_id = uuid4().hex
      async with self._lock:
          self._current_request_id = request_id
          try:
              if stream:
                  return self._stream_generate(prompt, system)
              else:
                  return await self._blocking_generate(prompt, system)
          finally:
              self._current_request_id = None

  # 채팅(최고 우선순위, 사용자 대면)의 경우:
  # 잠금은 기본적으로 FIFO 순서를 보장.
  # 진정한 우선순위를 위해 PriorityLock으로 래핑:

  class PriorityLock:
      """우선순위 대기자가 큐를 건너뛸 수 있는 asyncio.Lock."""
      _high_priority_queue: asyncio.Queue
      _normal_queue: asyncio.Queue
      _held: bool = False

      async def acquire(self, priority: str = "normal"):
          # 높은 우선순위 대기자가 일반 대기자보다 먼저 서비스됨
          ...
```

---

## 5. 하드코딩 근절 전략

### 5.1 설정값 분류

**왜 분류가 필요한가:** 모든 설정을 같은 방식으로 다루면 보안 위험(시크릿이 config.json에 노출)이나 UX 저하(포트 변경에 재시작 불필요한 것처럼 보임)가 발생한다. 값의 성격에 따라 저장 위치와 전파 방법을 명확히 구분한다.

| 카테고리 | 저장 위치 | 전파 방법 | 변경 유형 |
|---------|----------|----------|----------|
| **시크릿** | `.env` 파일 | `python-dotenv` -> `Config` 클래스 | 재시작 필요 (환경변수) |
| **사용자 선호** | `config.json` | `Config` 클래스 -> DI -> 서비스 | API를 통한 핫 리로드 |
| **플랫폼 상수** | `config.json` (platforms 섹션) | `Config` -> PlatformAdapter | 핫 리로드 (base_url 제외) |
| **행동 파라미터** | `config.json` (behavior 섹션) | `Config` -> StrategyEngine | 핫 리로드 |
| **UI 텍스트** | 프론트엔드 i18n 파일 + config.bot.name | Config API -> React context | 핫 리로드 |
| **Rate Limit** | `config.json` + 플랫폼 기본값 | `Config` -> RateLimiterFactory | 핫 리로드 |
| **기본값/폴백** | Python constants 모듈 | 모듈 수준 import | 코드 변경 (의도적) |
| **LLM 성격** | Ollama Modelfile (SYSTEM 프롬프트) | `ollama show` -> LLMService | 모델 변경 시 리로드 |

### 5.2 각 저장소별 내용

**`.env` (시크릿만, 커밋 금지):**
```
WEB_UI_PASSWORD_HASH=pbkdf2:...
MOLTBOOK_API_KEY=moltbook_xxxxx
BOTMADANG_API_KEY=yyyyy
```

**`config.json` (시크릿이 아닌 모든 선호설정):**
```
기획서 섹션 13의 모든 것: bot.*, platforms.*, behavior.*, voice.*, web_security.*, security.*, ui.*
```

**`app/core/constants.py` (하드코딩이지만 의도적인 기본값):**
```python
# config.json에 키가 누락될 때의 폴백 값.
# 사용자 커스터마이징이 아닌 합리적 기본값을 나타냄.

DEFAULT_MONITORING_INTERVAL_MINUTES = 30
DEFAULT_SESSION_TIMEOUT_HOURS = 24
DEFAULT_MAX_LOGIN_ATTEMPTS = 5
DEFAULT_LOCKOUT_MINUTES = 5
DEFAULT_BUSY_TIMEOUT_MS = 5000
MAX_BACKOFF_SECONDS = 1800  # 30분
DEFAULT_JITTER_RANGE = (30, 300)
HEALTH_CHECK_INTERVAL_SECONDS = 30
KILL_SWITCH_FILE = "STOP_BOT"
LOG_MAX_SIZE_BYTES = 100 * 1024 * 1024  # 100MB
LOG_RETENTION_DAYS = 30
BACKUP_RETENTION_DAYS = 7
MIN_COMMENT_LENGTH = 20
DEFAULT_KOREAN_RATIO_THRESHOLD = 0.7
```

### 5.3 Config 전파 체인

```
.env 파일                    config.json 파일
    |                              |
    v                              v
python-dotenv               json.load()
    |                              |
    v                              v
os.environ["KEY"]           raw dict
    |                              |
    +----------+-------------------+
               |
               v
        Config class (싱글톤)
         - Pydantic으로 검증
         - env + json 병합
         - 타입이 지정된 접근 제공: config.behavior.monitoring_interval_minutes
         - Observable: 변경 시 구독자에게 알림
               |
               v
        FastAPI Depends (get_config)
               |
    +----------+----------+----------+
    |          |          |          |
    v          v          v          v
 Services  Adapters  Middleware  Repositories
```

### 5.4 런타임 vs 재시작 필요 변경사항

| 변경 항목 | 런타임? | 이유 |
|----------|---------|-----|
| 모니터링 주기 | 예 | Scheduler가 타이머 재설정 |
| 관심 키워드 | 예 | StrategyEngine이 다음 평가 시 재읽기 |
| 일일 한도 | 예 | 각 작업 시도 시 확인 |
| 활동 시간 | 예 | Scheduler가 다음 틱에서 재평가 |
| 차단 키워드 | 예 | SecurityFilter가 패턴 재컴파일 |
| 플랫폼 활성화/비활성화 | 예 | PlatformRegistry가 활성 집합 갱신 |
| 음성 활성화/비활성화 | 예 | VoiceService가 파이프라인 시작/중지 |
| 세션 타임아웃 | 예 | AuthMiddleware가 각 요청 시 읽기 |
| 허용 IP | 예 | IPFilterMiddleware가 각 요청 시 읽기 |
| 테마/언어 | 예 | 프론트엔드가 변경 이벤트 시 API에서 읽기 |
| 봇 이름 | 예 | 프론트엔드가 API에서 읽기, 백엔드가 프롬프트에 사용 |
| Ollama 모델 | 예 | LLMService가 다음 요청에서 모델 전환 |
| 서버 포트/호스트 | **아니오** | uvicorn 재시작 필요 |
| 데이터베이스 경로 | **아니오** | 재연결 필요 |
| 플랫폼 base_url | **아니오** | 어댑터 재초기화 필요 |
| HTTPS 활성화 | **아니오** | 새 SSL 컨텍스트로 서버 재시작 필요 |

---

## 6. 최적 빌드 순서

### 6.1 빌드 단계별 근거

각 단계는 이전 단계 위에 구축된다. 단계 내에서 항목은 의존성 순서로 나열된다.

**왜 이 순서인가:** 각 단계가 다음 단계의 기반을 제공하도록 설계되었다. Config와 DB 없이는 어떤 서비스도 동작할 수 없고, 인증 없이는 어떤 라우트도 안전하지 않으며, 어댑터 없이는 봇의 핵심 목적(플랫폼 상호작용)을 달성할 수 없다.

```
PHASE 1: 스켈레톤 (1주차)
===========================
목표: 설정을 로드하고 health를 반환하는 실행 가능한 FastAPI 서버.

  1.1  constants.py + exceptions.py
       왜 먼저: 모든 다른 모듈이 이것을 import. 의존성 제로.

  1.2  config.py (Pydantic 검증, .env + config.json 로딩)
       왜 두 번째: 모든 것이 config를 필요로 함. 지금 견고하게 구축.
       산출물: 타입이 지정된 config 접근, 잘못된 config에 대한 검증 에러.

  1.3  logging.py (구조화된 로거 팩토리)
       의존: config (로그 레벨, 로테이션 설정)
       산출물: 이 시점 이후 어디서나 일관된 로깅.

  1.4  models/ (모든 Pydantic 도메인 모델)
       의존: constants (enum)
       왜 지금: 모든 서비스, 리포지토리, 라우트가 이것을 사용. 어휘를 정의.

  1.5  database.py (커넥션 풀, WAL 모드, 쓰기 잠금, 마이그레이션 러너)
       의존: config, logging
       산출물: 스키마가 생성된 작동하는 DB.

  1.6  main.py (lifespan을 가진 기본 FastAPI 앱, health 라우트만)
       의존: config, logging, database
       산출물: `GET /api/health`가 {"status": "healthy"} 반환
       테스트: curl localhost:5000/api/health


PHASE 2: 인증 + 보안 (2주차)
===================================
목표: 웹 UI가 비밀번호로 보호됨. 로그인 없이 봇에 접근 불가.

  2.1  auth_service.py (비밀번호 해싱, 세션 토큰, 로그인 시도 추적)
       의존: config, database
       산출물: 로그인/로그아웃 로직.

  2.2  middleware/auth.py + middleware/logging.py + IP 필터
       의존: auth_service, config
       산출물: 모든 요청이 인증됨 (/health와 /login 제외).

  2.3  routes/auth.py (POST /api/auth/login, POST /api/auth/logout)
       의존: auth_service, DI
       산출물: 작동하는 로그인 흐름.

  2.4  core/security.py (3단계 콘텐츠 필터)
       의존: config (차단 키워드/패턴)
       산출물: 전략과 라우트에서 사용할 준비된 필터 엔진.

  2.5  dependencies.py (FastAPI Depends 프로바이더, 초기 세트)
       의존: config, database, auth_service
       산출물: 이후 모든 라우트를 위한 깔끔한 DI 패턴 확립.

  테스트: 비밀번호로 로그인, 세션 쿠키 획득, 보호된 라우트 접근.


PHASE 3: 데이터 레이어 (2-3주차)
================================
목표: 모든 리포지토리 작동. 활동, 대화 등을 저장/조회 가능.

  3.1  repositories/base.py (공통 CRUD를 가진 BaseRepository)
       의존: database, models

  3.2  모든 리포지토리 구현 (conversation, activity, notification, collected_info, settings)
       의존: base repo, models
       산출물: 완전한 데이터 접근 레이어.

  테스트: 인메모리 SQLite로 각 리포지토리 단위 테스트.


PHASE 4: HTTP 클라이언트 + Rate Limiter (3주차)
==============================================
목표: 외부 플랫폼에 안전하게 API 호출 가능.

  4.1  http_client.py (재시도/백오프가 있는 aiohttp 세션 팩토리)
       의존: config, logging, exceptions
       산출물: 지수 백오프를 가진 탄력적 HTTP 클라이언트.

  4.2  rate_limiter.py (플랫폼별 Rate Limit 적용)
       의존: config, logging, models
       산출물: 봇마당과 Moltbook용 Rate Limiter.

  4.3  task_queue.py (Rate Limit 작업용 우선순위 비동기 큐)
       의존: rate_limiter, logging, events
       산출물: 모든 플랫폼 쓰기 작업을 위한 중앙화된 큐.

  테스트: Rate Limiter 단위 테스트 (시간 모킹). 동시 프로듀서로 큐 스트레스 테스트.


PHASE 5: 플랫폼 어댑터 (3-4주차)
=======================================
목표: 두 플랫폼에서 읽기/쓰기 가능.

  5.1  platforms/base.py (PlatformAdapter ABC + capability enum)
       의존: models, exceptions, rate_limiter, http_client

  5.2  platforms/botmadang.py
       의존: platform_base, config, security_filters
       산출물: 등록 흐름을 포함한 전체 봇마당 API 통합.

  5.3  platforms/moltbook.py
       의존: platform_base, config, security_filters
       산출물: 시맨틱 검색을 포함한 전체 Moltbook API 통합.

  5.4  platforms/registry.py (팩토리 + 런타임 활성화/비활성화)
       의존: all adapters, config
       산출물: 모든 플랫폼 작업을 위한 단일 진입점.

  5.5  routes/platforms.py (플랫폼 상태, 등록 엔드포인트)
       의존: platform_registry, DI

  테스트: 각 플랫폼에 대해 모킹된 HTTP 응답으로 통합 테스트.


PHASE 6: LLM 서비스 (4주차)
===============================
목표: 봇이 Ollama를 사용하여 텍스트 생성 가능.

  6.1  services/llm.py (Ollama chat/generate, 모델 목록, 헬스 체크, 스트리밍)
       의존: config, http_client, logging, task_queue (직렬화용)
       산출물: 스트리밍 지원을 가진 작동하는 LLM 통합.

  6.2  routes/chat.py + ws/chat.py (채팅 엔드포인트)
       의존: llm_service, conversation_repo, DI
       산출물: 사용자가 웹 UI에서 봇과 채팅 가능.

  테스트: 봇과 채팅, WebSocket을 통한 응답 스트리밍 검증.


PHASE 7: 이벤트 시스템 + WebSocket (4-5주차)
===============================================
목표: 실시간 업데이트가 백엔드에서 프론트엔드로 흐름.

  7.1  core/events.py (EventBus + 모든 이벤트 타입 정의)
       의존: models
       산출물: 디커플링된 이벤트 시스템.

  7.2  api/websocket/manager.py (연결 레지스트리 + 브로드캐스트)
       의존: events, auth_service
       산출물: 다중 클라이언트 WebSocket 관리.

  7.3  api/websocket/status.py (실시간 상태 업데이트)
       의존: ws_manager, events, health_monitor
       산출물: 프론트엔드가 실시간 상태 변경을 볼 수 있음.

  테스트: 두 브라우저 탭 열고, 양쪽 모두 상태 업데이트 수신 확인.


PHASE 8: 전략 엔진 (5-6주차)
=====================================
목표: 봇이 댓글/게시/추천에 대한 자율적 결정 가능.

  8.1  services/strategy.py (BehaviorStrategy ABC + DefaultBehaviorStrategy + StrategyEngine)
       의존: config, models, activity_repo, security_filters, llm_service, events
       산출물: 기획서 섹션 5.2-5.6에 따른 완전한 의사결정 엔진.

  8.2  services/translation.py (LLM을 통한 한국어 <-> 영어)
       의존: llm_service, task_queue
       산출물: 크로스 플랫폼 콘텐츠를 위한 번역 기능.

  테스트: 모킹된 LLM 응답으로 단위 테스트. 의사결정 트리 로직 검증.


PHASE 9: 자동화 (6-7주차)
================================
목표: 봇이 자율적으로 운영.

  9.1  services/feed_monitor.py (주기적 피드 스캔)
       의존: platform_registry, config, strategy_engine, activity_repo, events, task_queue

  9.2  services/notifications.py (알림 폴링 + 자동 응답)
       의존: platform_registry, notification_repo, activity_repo, strategy_engine, events, task_queue

  9.3  services/scheduler.py (모든 주기적 작업용 Cron 유사 스케줄러)
       의존: config, feed_monitor, notification_service, logging, events

  9.4  services/kill_switch.py (긴급 정지: 파일 + API)
       의존: scheduler, task_queue, events, config

  9.5  services/health.py (주기적 헬스 모니터링)
       의존: config, llm_service, database, platform_registry

  9.6  routes/emergency.py, routes/activities.py, routes/notifications.py,
       routes/settings.py, routes/commands.py, routes/info.py, routes/backup.py
       의존: 각 서비스 + DI

  테스트: 엔드투엔드: 봇이 게시글 발견 -> 댓글 생성 -> 큐에 추가 -> 쿨다운 후 게시.


PHASE 10: 설정 마법사 (7주차)
=================================
목표: 최초 설정이 엔드투엔드로 작동.

  10.1 routes/setup_wizard.py (다단계 마법사 API)
       의존: config, auth_service, platform_registry, llm_service
       산출물: 기획서 섹션 14에 따른 완전한 초기 설정 흐름.

  테스트: 새 설치, 마법사 완료, 봇 운영 시작.


PHASE 11: 프론트엔드 (7-10주차)
================================
목표: 전체 React UI.

  11.1 프로젝트 스캐폴딩 (Vite + React + Tailwind + shadcn/ui)
  11.2 인증 페이지 (로그인, 초기 비밀번호 설정)
  11.3 채팅 탭 (WebSocket과 메신저 스타일 UI)
  11.4 상태 바 (VRAM, 플랫폼 상태, 봇 상태)
  11.5 설정 탭 (핫 리로드를 지원하는 모든 설정 섹션)
  11.6 활동 로그 탭 (타임라인, 필터, 상세 모달)
  11.7 정보 수집 탭 (카테고리, 검색, 북마크)
  11.8 설정 마법사 UI (다단계 폼)
  11.9 승인 UI (WebSocket을 통한 승인/거부/수정 모달)
  11.10 슬래시 명령어 (채팅 입력의 자동완성)
  11.11 알림 표시 (WebSocket의 실시간)


PHASE 12: 음성 (10-11주차, 선택사항)
========================================
목표: 음성 입력 작동.

  12.1 services/voice.py (오케스트레이터: wake word + whisper 조율)
  12.2 voice/wake_word.py (openWakeWord 래퍼)
  12.3 voice/whisper.py (Whisper 로드/언로드/변환)
  12.4 api/websocket/audio.py (오디오 스트리밍 엔드포인트)
  12.5 프론트엔드 오디오 캡처 (MediaStream + WebSocket)

  테스트: Wake Word 말하기, 명령 말하기, 채팅에 텍스트 표시 검증.


PHASE 13: 폴리싱 (11-12주차)
===============================
  13.1 백업/복구 (JSON 내보내기/가져오기)
  13.2 로그 로테이션 + 디스크 모니터링
  13.3 자동 백업 (일일)
  13.4 UI의 종합적 에러 메시지
  13.5 성능 프로파일링 + 최적화
  13.6 문서화 (README, SETUP, CREATE_BOT, API 문서)
```

### 6.2 빌드 순서 근거 요약

| 단계 | 이 순서의 이유 |
|------|--------------|
| 1 (스켈레톤) | Config + DB + 모델은 말 그대로 모든 곳에서 import됨. 한 번 구축하고 영원히 사용. |
| 2 (인증) | 보안은 타협 불가. 이후 모든 라우트에 인증 미들웨어 필요. 인증을 늦게 구축하면 모든 라우트를 레트로핏. |
| 3 (데이터 레이어) | 리포지토리는 모든 서비스에서 사용. 단순하고 테스트 가능하며 데이터 백본 제공. |
| 4 (HTTP + Rate) | 플랫폼 통신 인프라. 어댑터 이전에 필요. |
| 5 (플랫폼 어댑터) | 봇의 전체 목적이 플랫폼 상호작용. 서비스가 유용한 일을 하려면 어댑터 필요. |
| 6 (LLM) | 봇의 "두뇌". 전략 엔진, 채팅, 번역 모두 이것에 의존. |
| 7 (이벤트 + WS) | 실시간 UI 업데이트. 이것 없이는 프론트엔드가 백엔드 활동에 대해 아무것도 모름. |
| 8 (전략) | 의사결정 핵심. LLM + 리포지토리 + 어댑터(모두 구축됨)에 의존. |
| 9 (자동화) | 모든 것을 연결. 스케줄러, 모니터, 킬 스위치. |
| 10 (마법사) | 최초 UX. 모든 서비스가 존재한 후에 구축하여 마법사가 실제 연결 테스트 가능. |
| 11 (프론트엔드) | 이전 모든 단계의 안정적 API 계약에 의존하므로 마지막에 구축. |
| 12 (음성) | 선택사항이고 복잡하며 다른 기능에 대한 의존이 가장 적음. |

---

## 7. 백엔드 파일 구조

**왜 이 구조인가:** 레이어 아키텍처(섹션 2)를 디렉토리 구조에 직접 반영한다. `core/`는 Infrastructure Layer, `models/`는 Domain Layer, `repositories/`와 `platforms/`는 Adapter Layer, `services/`는 Service Layer, `api/`는 Application Layer이다. 개발자가 파일 위치만으로 해당 코드의 레이어와 책임을 즉시 파악할 수 있다.

```
backend/
|-- requirements.txt
|-- requirements-dev.txt          # pytest, httpx, aiosqlite[testing] 등
|-- pyproject.toml                # 프로젝트 메타데이터, 도구 설정
|-- alembic.ini                   # (선택) alembic 마이그레이션 사용 시
|-- app/
|   |-- __init__.py
|   |-- main.py                   # FastAPI 앱 팩토리, lifespan, 라우트 마운트
|   |
|   |-- core/                     # INFRASTRUCTURE LAYER
|   |   |-- __init__.py
|   |   |-- config.py             # Config 싱글톤: .env + config.json + 검증
|   |   |-- constants.py          # Enum, 기본값, 센티넬 값
|   |   |-- exceptions.py         # 커스텀 예외 계층
|   |   |-- logging.py            # 구조화된 로거 팩토리 + 로테이션 설정
|   |   |-- database.py           # SQLite 커넥션 풀, WAL, 쓰기 잠금, 마이그레이션
|   |   |-- http_client.py        # aiohttp 세션 팩토리 (재시도/백오프)
|   |   |-- rate_limiter.py       # 플랫폼별 Rate Limit 적용
|   |   |-- task_queue.py         # Rate Limit 작업용 우선순위 비동기 큐
|   |   |-- security.py           # 3단계 콘텐츠 필터링 엔진
|   |   |-- events.py             # 이벤트 버스 + 이벤트 타입 정의
|   |   |-- ssl.py                # HTTPS용 자체 서명 인증서 생성
|   |   |-- migrations/           # SQL 마이그레이션 스크립트
|   |   |   |-- __init__.py
|   |   |   |-- 001_initial_schema.sql
|   |   |   |-- 002_add_indexes.sql
|   |   |   +-- ...
|   |
|   |-- models/                   # DOMAIN LAYER - 순수 데이터 구조
|   |   |-- __init__.py           # 모든 모델 re-export
|   |   |-- base.py               # BaseModel 설정 (예: orm_mode)
|   |   |-- conversation.py       # Conversation, ConversationCreate
|   |   |-- activity.py           # Activity, ActivityCreate, DailyCounts
|   |   |-- notification.py       # NotificationLog, NotificationCreate
|   |   |-- collected_info.py     # CollectedInfo, CollectedInfoCreate
|   |   |-- settings.py           # SettingsSnapshot
|   |   |-- platform.py           # PlatformPost, PlatformComment, PlatformNotification 등
|   |   |-- auth.py               # Session, LoginRequest, LoginResponse
|   |   |-- health.py             # HealthCheckResult, ComponentHealth
|   |   |-- events.py             # 이벤트 페이로드 dataclass
|   |   |-- config_schema.py      # config.json 구조를 미러링하는 Pydantic 모델
|   |   +-- enums.py              # ActivityType, Platform, BotStatus 등
|   |
|   |-- repositories/            # DATA ACCESS LAYER
|   |   |-- __init__.py
|   |   |-- base.py              # BaseRepository: execute, fetch_one, fetch_all
|   |   |-- conversation.py
|   |   |-- activity.py
|   |   |-- notification.py
|   |   |-- collected_info.py
|   |   +-- settings.py
|   |
|   |-- platforms/               # ADAPTER LAYER - 외부 플랫폼 통합
|   |   |-- __init__.py
|   |   |-- base.py              # PlatformAdapter ABC + PlatformCapability enum
|   |   |-- botmadang.py         # 봇마당 구현체
|   |   |-- moltbook.py          # Moltbook 구현체
|   |   +-- registry.py          # PlatformRegistry: 팩토리, 활성화/비활성화, 조회
|   |
|   |-- services/               # SERVICE LAYER - 모든 비즈니스 로직
|   |   |-- __init__.py
|   |   |-- llm.py              # Ollama 상호작용: generate, chat, models, health
|   |   |-- auth.py             # 비밀번호 해싱, 세션, 로그인 시도
|   |   |-- strategy.py         # BehaviorStrategy ABC, DefaultStrategy, StrategyEngine
|   |   |-- notifications.py    # 알림 폴링 + 자동 응답 디스패치
|   |   |-- feed_monitor.py     # 주기적 피드 스캔 + 게시글 평가
|   |   |-- translation.py      # LLM을 통한 한국어 <-> 영어 번역
|   |   |-- backup.py           # DB + 설정의 JSON 내보내기/가져오기
|   |   |-- scheduler.py        # 주기적 작업용 Cron 유사 스케줄러
|   |   |-- kill_switch.py      # 긴급 정지: 파일 기반 + API 기반
|   |   |-- health.py           # 주기적 헬스 체크: Ollama, DB, 플랫폼, VRAM
|   |   +-- voice.py            # 음성 오케스트레이션 (선택, voice/에 위임)
|   |
|   |-- api/                    # APPLICATION LAYER
|   |   |-- __init__.py
|   |   |-- dependencies.py     # 모든 서비스용 FastAPI Depends 프로바이더
|   |   |
|   |   |-- middleware/
|   |   |   |-- __init__.py
|   |   |   |-- auth.py         # 세션 검증, 면제 경로
|   |   |   |-- ip_filter.py    # IP 허용목록 적용
|   |   |   +-- request_log.py  # 요청/응답 로깅
|   |   |
|   |   |-- routes/
|   |   |   |-- __init__.py
|   |   |   |-- auth.py         # POST /api/auth/login, /logout
|   |   |   |-- chat.py         # POST /api/chat, GET /api/chat/history
|   |   |   |-- platforms.py    # GET /api/platforms, POST /api/platforms/register
|   |   |   |-- activities.py   # GET /api/activities (타임라인, 필터)
|   |   |   |-- settings.py     # GET/PUT /api/settings
|   |   |   |-- notifications.py # GET /api/notifications
|   |   |   |-- info.py         # GET /api/collected-info, 북마크, 검색
|   |   |   |-- health.py       # GET /api/health (인증 불필요)
|   |   |   |-- emergency.py    # POST /api/emergency-stop
|   |   |   |-- backup.py       # POST /api/backup/export, /import
|   |   |   |-- commands.py     # POST /api/commands (슬래시 명령)
|   |   |   +-- setup_wizard.py # GET/POST /api/setup/* (다단계 마법사)
|   |   |
|   |   +-- websocket/
|   |       |-- __init__.py
|   |       |-- manager.py      # 연결 레지스트리, 브로드캐스트, 상태 동기화
|   |       |-- chat.py         # WS /ws/chat (LLM 스트리밍 실시간 채팅)
|   |       |-- status.py       # WS /ws/status (실시간 상태 업데이트)
|   |       +-- audio.py        # WS /ws/audio (음성용 오디오 스트리밍)
|   |
|   +-- voice/                  # VOICE SUBSYSTEM (선택)
|       |-- __init__.py
|       |-- wake_word.py        # openWakeWord / Porcupine 래퍼
|       +-- whisper.py          # Whisper 모델 관리: 로드/언로드/변환
|
|-- tests/
|   |-- __init__.py
|   |-- conftest.py             # 공유 픽스처: 테스트 config, 인메모리 DB, 모킹 HTTP
|   |-- unit/
|   |   |-- __init__.py
|   |   |-- test_config.py
|   |   |-- test_rate_limiter.py
|   |   |-- test_security_filters.py
|   |   |-- test_task_queue.py
|   |   |-- test_strategy.py
|   |   |-- test_events.py
|   |   |-- repositories/
|   |   |   |-- test_activity_repo.py
|   |   |   |-- test_conversation_repo.py
|   |   |   |-- test_notification_repo.py
|   |   |   +-- ...
|   |   +-- services/
|   |       |-- test_llm_service.py
|   |       |-- test_auth_service.py
|   |       |-- test_strategy_engine.py
|   |       +-- ...
|   |-- integration/
|   |   |-- __init__.py
|   |   |-- test_platform_botmadang.py
|   |   |-- test_platform_moltbook.py
|   |   |-- test_feed_to_comment_flow.py
|   |   |-- test_notification_response_flow.py
|   |   +-- test_setup_wizard_flow.py
|   +-- fixtures/
|       |-- mock_responses/
|       |   |-- botmadang_posts.json
|       |   |-- botmadang_notifications.json
|       |   |-- moltbook_posts.json
|       |   |-- moltbook_search.json
|       |   +-- ollama_generate.json
|       +-- test_config.json
|
|-- personalities/
|   |-- bara.Modelfile
|   |-- helper.Modelfile
|   +-- custom.Modelfile.template
|
|-- config.example.json
|-- .env.example
+-- .gitignore
```

---

## 8. 프론트엔드 파일 구조

**왜 이 구조인가:** 프론트엔드 내부도 레이어 구조를 따른다. `types/`(타입 정의) -> `services/`(API 클라이언트) -> `stores/`(상태 관리) -> `hooks/`(React 훅) -> `components/`(UI 컴포넌트) 순서로 의존하며, 각 디렉토리가 명확한 책임을 갖는다. 백엔드 Pydantic 모델을 TypeScript 타입으로 미러링하여 API 계약을 보장한다.

```
frontend/
|-- package.json
|-- vite.config.ts
|-- tsconfig.json
|-- tailwind.config.ts
|-- index.html
|-- .env.example                   # VITE_API_URL=https://localhost:5000
|-- public/
|   +-- favicon.ico
|
+-- src/
    |-- main.tsx                    # 앱 진입점: React root + providers
    |-- App.tsx                     # 루트 레이아웃: 인증 게이트 + 탭 라우터
    |-- vite-env.d.ts
    |
    |-- types/                      # 공유 타입 정의
    |   |-- index.ts                # re-exports
    |   |-- api.ts                  # API 요청/응답 타입 (백엔드 Pydantic 미러)
    |   |-- models.ts               # 도메인 모델: Activity, Conversation 등
    |   |-- events.ts               # WebSocket 이벤트 페이로드 타입
    |   |-- config.ts               # Config 형태 (백엔드 config_schema 미러)
    |   +-- enums.ts                # Platform, ActivityType, BotStatus 등
    |
    |-- services/                   # API 클라이언트 레이어
    |   |-- api.ts                  # 기본 HTTP 클라이언트 (인증 쿠키 포함 fetch 래퍼)
    |   |-- auth.api.ts             # login(), logout()
    |   |-- chat.api.ts             # sendMessage(), getHistory()
    |   |-- platforms.api.ts        # getPlatforms(), registerBotmadang()
    |   |-- activities.api.ts       # getActivities(), getTimeline()
    |   |-- settings.api.ts         # getSettings(), updateSettings()
    |   |-- notifications.api.ts    # getNotifications()
    |   |-- info.api.ts             # getCollectedInfo(), toggleBookmark()
    |   |-- health.api.ts           # getHealth()
    |   |-- commands.api.ts         # executeCommand()
    |   |-- backup.api.ts           # exportBackup(), importBackup()
    |   +-- setup.api.ts            # 마법사 단계 API
    |
    |-- hooks/                      # 커스텀 React 훅
    |   |-- useWebSocket.ts         # WebSocket 연결 + 재연결 로직
    |   |-- useAuth.ts              # 로그인 상태, 세션 관리
    |   |-- useConfig.ts            # Config 조회 + 핫 리로드 구독
    |   |-- useBotStatus.ts         # WS의 실시간 봇 상태
    |   |-- useActivities.ts        # 페이지네이션 + 필터가 있는 활동 목록
    |   |-- useNotifications.ts     # 실시간 알림 표시
    |   |-- useChat.ts              # 채팅 상태, 메시지 히스토리, 스트리밍
    |   |-- useAudio.ts             # MediaStream + WS 오디오 스트리밍
    |   |-- useApproval.ts          # 승인 요청 처리
    |   +-- useSlashCommands.ts     # 명령 자동완성 + 실행
    |
    |-- stores/                     # 상태 관리 (Zustand 또는 React Context)
    |   |-- authStore.ts            # 인증 상태: isLoggedIn, session
    |   |-- configStore.ts          # Config 상태: 봇 이름, 설정
    |   |-- chatStore.ts            # 채팅 메시지, 스트리밍 상태
    |   |-- statusStore.ts          # 봇 상태, 플랫폼 연결, VRAM
    |   |-- activityStore.ts        # 활동 타임라인 캐시
    |   |-- notificationStore.ts    # 대기 중 알림, 미읽음 수
    |   +-- approvalStore.ts        # 대기 중 승인 요청
    |
    |-- components/                 # UI 컴포넌트
    |   |-- layout/
    |   |   |-- AppShell.tsx        # 메인 앱 셸: 사이드바/헤더 + 콘텐츠 영역
    |   |   |-- TabBar.tsx          # 채팅 | 활동 | 정보 | 설정 탭
    |   |   |-- StatusBar.tsx       # 하단 바: VRAM, 플랫폼 상태, 봇 상태
    |   |   +-- Header.tsx          # 봇 이름이 포함된 앱 헤더
    |   |
    |   |-- auth/
    |   |   |-- LoginPage.tsx       # 비밀번호 로그인 폼
    |   |   +-- AuthGate.tsx        # 래퍼: 인증 상태에 따라 로그인 또는 앱 표시
    |   |
    |   |-- chat/
    |   |   |-- ChatPage.tsx        # 채팅 탭 컨테이너
    |   |   |-- MessageList.tsx     # 스크롤 가능한 메시지 목록
    |   |   |-- MessageBubble.tsx   # 단일 메시지 말풍선 (사용자/봇/시스템)
    |   |   |-- ActivityBubble.tsx  # 인라인 SNS 활동 알림 (클릭 가능)
    |   |   |-- ChatInput.tsx       # 텍스트 입력 + 전송 버튼 + 음성 버튼
    |   |   |-- StreamingIndicator.tsx  # "봇이 입력 중..." 인디케이터
    |   |   +-- SlashCommandMenu.tsx    # /명령어 자동완성 팝업
    |   |
    |   |-- activity/
    |   |   |-- ActivityPage.tsx    # 활동 로그 탭 컨테이너
    |   |   |-- Timeline.tsx        # 활동의 수직 타임라인
    |   |   |-- TimelineItem.tsx    # 타임라인의 단일 활동
    |   |   |-- ActivityFilters.tsx # 날짜, 플랫폼, 타입 필터
    |   |   |-- ActivityDetail.tsx  # 모달: 전체 활동 상세
    |   |   +-- DailySummary.tsx    # "오늘: 댓글 5개, 글 2개, 추천 10개"
    |   |
    |   |-- info/
    |   |   |-- InfoPage.tsx        # 정보 수집 탭 컨테이너
    |   |   |-- InfoList.tsx        # 수집된 정보 항목 목록
    |   |   |-- InfoCard.tsx        # 단일 정보 항목 카드
    |   |   |-- InfoFilters.tsx     # 카테고리, 검색, 북마크 필터
    |   |   +-- InfoDetail.tsx      # 모달: 전체 정보 상세
    |   |
    |   |-- settings/
    |   |   |-- SettingsPage.tsx    # 설정 탭 컨테이너
    |   |   |-- BotSettings.tsx     # 봇 이름, 모델 선택
    |   |   |-- PlatformSettings.tsx # 플랫폼 활성화/비활성화, API 키
    |   |   |-- BehaviorSettings.tsx # 키워드, 한도, 스케줄, 지터
    |   |   |-- VoiceSettings.tsx   # 음성 on/off, wake words, 마이크 소스
    |   |   |-- SecuritySettings.tsx # 차단 키워드, 패턴
    |   |   |-- DataManagement.tsx  # 백업/복구, 긴급 정지
    |   |   +-- ScheduleEditor.tsx  # 활동 시간 시각적 편집기
    |   |
    |   |-- setup/
    |   |   |-- SetupWizard.tsx     # 다단계 마법사 컨테이너
    |   |   |-- StepPassword.tsx
    |   |   |-- StepSystemCheck.tsx
    |   |   |-- StepModelSelect.tsx
    |   |   |-- StepBotName.tsx
    |   |   |-- StepWakeWords.tsx
    |   |   |-- StepPlatforms.tsx
    |   |   |-- StepKeywords.tsx
    |   |   |-- StepSchedule.tsx
    |   |   |-- StepVoice.tsx
    |   |   +-- StepComplete.tsx
    |   |
    |   |-- approval/
    |   |   |-- ApprovalModal.tsx   # 승인/거부/수정 모달
    |   |   +-- ApprovalQueue.tsx   # 대기 중 승인 목록
    |   |
    |   +-- common/
    |       |-- Button.tsx
    |       |-- Modal.tsx
    |       |-- Input.tsx
    |       |-- Badge.tsx
    |       |-- Toast.tsx           # 알림 토스트
    |       |-- LoadingSpinner.tsx
    |       |-- ErrorBoundary.tsx
    |       +-- ConnectionIndicator.tsx  # WS 연결 상태 점
    |
    +-- utils/
        |-- format.ts               # 날짜 포맷, 숫자 포맷
        |-- validation.ts           # 입력 검증 헬퍼
        |-- websocket.ts            # 재연결이 있는 WS 연결 클래스
        |-- audio.ts                # MediaStream + AudioContext 헬퍼
        +-- i18n.ts                 # 간단한 i18n (ko/en) + config.bot.name 보간
```

---

## 9. 테스트 전략

### 9.1 단위 테스트 대상

**왜 이 매트릭스인가:** 각 모듈별로 "무엇을 테스트하고 무엇을 Mock할지"를 명확히 정의하면 테스트 작성 시 판단 비용을 줄이고, Mock이 과도하거나 부족한 테스트를 방지한다.

| 모듈 | 테스트 대상 | Mock 대상 |
|------|-----------|----------|
| `config.py` | 모든 config 섹션 검증. 누락 키는 기본값 사용. 잘못된 값은 에러 발생. .env 로딩. 핫 리로드 알림. | 파일시스템 (임시 파일 사용) |
| `rate_limiter.py` | 쿨다운 적용. 자정 일일 카운터 리셋. API 호출 슬라이딩 윈도우. 동시 접근 안전성. | 시간 (`time.monotonic` monkeypatch) |
| `security.py` | Level 1 자동 차단 (API 키 패턴). Level 2 플래깅. Level 3 통과. 정규식 패턴 매칭. 한국어 비율 계산. | 없음 (순수 로직) |
| `task_queue.py` | 우선순위 정렬. 백오프 포함 재시도. 최대 재시도 소진. 동시 프로듀서 안전성. 드레인 동작. | Rate Limiter (항상 허용 또는 항상 거부로 mock) |
| `events.py` | 발행-구독. 다중 구독자. 구독 해제. 핸들러 예외가 버스를 크래시시키지 않음. | 없음 (순수 로직) |
| `strategy.py` | 댓글 의사결정 트리 (기획서 5.2). 품질 체크 (최소 길이, 한국어 비율, 관련성). 지터 범위. 일일 한도 적용. 게시글 주제-커뮤니티 매핑. | LLM 서비스, Activity Repo, Config |
| `auth_service.py` | 비밀번호 해싱/검증. 세션 토큰 생성/검증. 로그인 시도 추적. N회 실패 후 잠금. 세션 만료. | Database (인메모리 SQLite 사용) |
| `llm_service.py` | Generate 호출 구성. 스트리밍 응답 처리. 모델 전환. 헬스 체크. Lock 직렬화. | HTTP 클라이언트 (Ollama 응답 mock) |
| `kill_switch.py` | 파일 기반 정지 감지. API 기반 정지. 그레이스풀 셧다운 시퀀스. STOP_BOT 파일 생성/삭제. | Scheduler, Task Queue, 파일시스템 |
| 모든 리포지토리 | CRUD 작업. 쿼리 필터. 페이지네이션. `has_responded_to` 중복 확인. 일일 카운트 집계. | Database (실제 인메모리 SQLite 사용 - mock 아님) |
| 플랫폼 어댑터 | 요청 구성 (올바른 URL, 헤더). 응답 파싱. 에러 코드 처리 (401, 429, 500). Rate Limit 통합. 도메인 검증 (Moltbook 키는 www.moltbook.com으로만). | HTTP 클라이언트 (응답 mock) |

### 9.2 통합 테스트 접근

| 테스트 시나리오 | 실제 사용 | Mock 대상 |
|---------------|----------|----------|
| 피드-댓글 흐름 | DB, config, 전략 로직, Rate Limiter, Task Queue, Event Bus | 플랫폼 HTTP 응답, LLM 응답 |
| 알림-답글 흐름 | DB, config, Notification Service, 전략 | 플랫폼 HTTP, LLM |
| 설정 마법사 전체 흐름 | DB, config 파일 쓰기, Auth Service | 플랫폼 HTTP (등록), Ollama (모델 목록) |
| 인증 + 미들웨어 체인 | DB, Auth Service, FastAPI 테스트 클라이언트 | 없음 (풀 스택 테스트) |
| WebSocket 상태 동기화 | FastAPI 테스트 클라이언트, WS Manager, Event Bus | 서비스 (간소화된 스텁) |
| Config 핫 리로드 | Config, Observer 시스템, 서비스 | 없음 (실제 재초기화 테스트) |
| 긴급 정지 | Kill Switch, Scheduler, Task Queue | 플랫폼 어댑터 |

### 9.3 플랫폼 API Mock 전략

**픽스처 기반 접근:**

**왜 픽스처 기반인가:** JSON 파일로 응답을 관리하면 테스트 코드에서 응답 데이터를 분리하여 가독성을 높이고, 실제 API 응답을 캡처하여 픽스처로 저장하면 현실적인 테스트 데이터를 보장한다.

```
tests/fixtures/mock_responses/
  botmadang_posts.json         # GET /posts 응답
  botmadang_notifications.json # GET /notifications 응답
  botmadang_register.json      # POST /agents/register 응답
  botmadang_post_created.json  # POST /posts 응답
  botmadang_comment_created.json
  botmadang_error_429.json     # Rate Limit 에러
  botmadang_error_401.json     # 인증 에러
  moltbook_posts.json
  moltbook_search.json         # 시맨틱 검색 응답
  moltbook_error_429.json
  ollama_generate.json         # 논스트리밍 응답
  ollama_tags.json             # 모델 목록
  ollama_show.json             # SYSTEM 프롬프트 포함 모델 정보
```

**Mock HTTP 클라이언트 (conftest.py):**
```python
# aioresponses 또는 커스텀 MockHttpClient 사용
# URL 패턴 -> 픽스처 파일 매핑 등록

@pytest.fixture
def mock_botmadang():
    with aioresponses() as m:
        m.get(
            "https://botmadang.org/api/v1/posts",
            payload=load_fixture("botmadang_posts.json")
        )
        m.get(
            "https://botmadang.org/api/v1/notifications",
            payload=load_fixture("botmadang_notifications.json")
        )
        # ... 등
        yield m
```

**에러 시나리오 테스트:**

각 어댑터 테스트 스위트는 다음을 포함:
- Happy path (200 응답)
- 인증 실패 (401 -> 플랫폼 비활성화, 사용자 알림)
- Rate Limit (429 -> 지수 백오프)
- 서버 에러 (500 -> 3회 재시도 -> 회로 차단기)
- 네트워크 타임아웃 -> 오프라인 큐
- 잘못된 형식의 응답 -> 그레이스풀 디그레이데이션

### 9.4 테스트 설정

```python
# tests/conftest.py

@pytest.fixture
def test_config():
    """안전한 테스트 값을 가진 Config. 실제 API 키 없음."""
    return Config.from_dict({
        "bot": {"name": "TestBot", "model": "test-model", ...},
        "platforms": {
            "botmadang": {"enabled": True, "base_url": "https://botmadang.org/api/v1"},
            "moltbook": {"enabled": True, "base_url": "https://www.moltbook.com/api/v1"}
        },
        "behavior": {
            "monitoring_interval_minutes": 1,  # 테스트용 빠른 설정
            "daily_limits": {"max_comments": 5, "max_posts": 1, "max_upvotes": 5},
            ...
        }
    })

@pytest.fixture
async def test_db():
    """스키마가 적용된 인메모리 SQLite."""
    db = await Database.initialize_memory()
    await db.run_migrations()
    yield db
    await db.close()
```

---

## 10. 인터페이스 정의

### 10.1 PlatformAdapter (ABC)

**왜 ABC로 정의하는가:** 추상 기본 클래스를 통해 모든 플랫폼 구현체가 동일한 계약을 준수하도록 강제한다. 새 플랫폼 추가 시 이 인터페이스만 구현하면 시스템의 나머지 부분은 변경이 불필요하다.

```python
from abc import ABC, abstractmethod
from enum import Enum
from typing import Optional
from datetime import datetime


class PlatformCapability(Enum):
    SEMANTIC_SEARCH = "semantic_search"
    FOLLOW = "follow"
    NESTED_COMMENTS = "nested_comments"
    NOTIFICATIONS = "notifications"
    AGENT_REGISTRATION = "agent_registration"
    DOWNVOTE = "downvote"


class PlatformAdapter(ABC):
    """
    모든 플랫폼 통합을 위한 추상 인터페이스.
    각 플랫폼이 이 ABC를 구현한다. 시스템의 나머지는
    이 인터페이스를 통해서만 플랫폼과 상호작용한다.
    """

    @property
    @abstractmethod
    def platform_name(self) -> str:
        """고유 식별자: 'botmadang', 'moltbook'"""

    @property
    @abstractmethod
    def is_authenticated(self) -> bool:
        """어댑터가 유효한 인증 정보를 보유하는지 여부"""

    @abstractmethod
    def get_capabilities(self) -> set[PlatformCapability]:
        """이 플랫폼이 지원하는 기능. 호출자가 선택적 메서드 호출 전에 확인."""

    # --- AUTH ---

    @abstractmethod
    async def validate_credentials(self) -> bool:
        """현재 API 키가 유효한지 테스트. True/False 반환."""

    # --- READ OPERATIONS ---

    @abstractmethod
    async def get_posts(
        self,
        sort: str = "new",
        limit: int = 25,
        community: Optional[str] = None,
    ) -> list["PlatformPost"]:
        """게시글 조회. 표준화된 PlatformPost 목록 반환."""

    @abstractmethod
    async def get_post_detail(self, post_id: str) -> "PlatformPost":
        """전체 내용이 포함된 단일 게시글 조회."""

    @abstractmethod
    async def get_comments(self, post_id: str) -> list["PlatformComment"]:
        """게시글의 댓글 조회."""

    @abstractmethod
    async def get_communities(self) -> list["PlatformCommunity"]:
        """사용 가능한 커뮤니티 조회 (submadangs / submolts)."""

    @abstractmethod
    async def get_notifications(
        self,
        since: Optional[datetime] = None,
        unread_only: bool = True,
    ) -> list["PlatformNotification"]:
        """
        알림 조회. 알림을 지원하지 않는 플랫폼은
        빈 목록 반환 (capabilities를 먼저 확인).
        """

    async def search(
        self,
        query: str,
        semantic: bool = False,
        limit: int = 25,
    ) -> list["PlatformPost"]:
        """
        게시글 검색. `semantic=True`는 가능하면 시맨틱 검색 사용.
        기본 구현은 get_posts의 키워드 필터링으로 폴백.
        """
        if semantic and PlatformCapability.SEMANTIC_SEARCH not in self.get_capabilities():
            semantic = False
        posts = await self.get_posts(limit=limit)
        if not semantic:
            return [p for p in posts if query.lower() in (p.title + p.content).lower()]
        raise NotImplementedError("Subclass must implement semantic search")

    # --- WRITE OPERATIONS ---

    @abstractmethod
    async def create_post(
        self,
        title: str,
        content: str,
        community: str,
    ) -> "PlatformPostResult":
        """새 게시글 작성. 플랫폼 게시글 ID가 포함된 결과 반환."""

    @abstractmethod
    async def create_comment(
        self,
        post_id: str,
        content: str,
        parent_comment_id: Optional[str] = None,
    ) -> "PlatformCommentResult":
        """게시글에 댓글 작성. parent_comment_id로 대댓글."""

    @abstractmethod
    async def upvote(self, post_id: str) -> bool:
        """게시글 추천. 성공 여부 반환."""

    async def downvote(self, post_id: str) -> bool:
        """게시글 비추천. 기본적으로 NotImplementedError 발생."""
        raise NotImplementedError(f"{self.platform_name} does not support downvote")

    @abstractmethod
    async def mark_notifications_read(
        self,
        notification_ids: list[str] | str,  # "all" 또는 ID 목록
    ) -> bool:
        """알림을 읽음으로 표시."""

    # --- PLATFORM-SPECIFIC (선택) ---

    async def follow(self, agent_id: str) -> bool:
        """에이전트 팔로우. Moltbook 전용."""
        raise NotImplementedError(f"{self.platform_name} does not support follow")

    async def unfollow(self, agent_id: str) -> bool:
        """에이전트 언팔로우. Moltbook 전용."""
        raise NotImplementedError(f"{self.platform_name} does not support unfollow")

    async def register_agent(
        self, name: str, description: str
    ) -> "RegistrationResult":
        """새 에이전트 등록. 봇마당 전용."""
        raise NotImplementedError(f"{self.platform_name} does not support registration")

    # --- META ---

    @abstractmethod
    def get_rate_limit_config(self) -> "RateLimitConfig":
        """이 플랫폼의 Rate Limit 설정 반환."""
```

### 10.2 Repository 인터페이스

```python
from abc import ABC, abstractmethod
from typing import TypeVar, Generic, Optional
from datetime import datetime, date

T = TypeVar("T")
C = TypeVar("C")  # Create 모델


class BaseRepository(ABC, Generic[T, C]):
    """
    공통 데이터베이스 작업을 제공하는 기본 리포지토리.
    T = 도메인 모델 타입, C = 생성 입력 타입.
    """

    @abstractmethod
    async def add(self, item: C) -> T:
        """새 레코드 삽입. 생성된 도메인 모델 반환."""

    @abstractmethod
    async def get_by_id(self, id: int) -> Optional[T]:
        """기본 키로 단일 레코드 조회."""

    @abstractmethod
    async def delete(self, id: int) -> bool:
        """기본 키로 레코드 삭제. 삭제 시 True 반환."""


class ConversationRepositoryInterface(BaseRepository["Conversation", "ConversationCreate"]):

    @abstractmethod
    async def get_history(
        self,
        limit: int = 50,
        offset: int = 0,
        platform_filter: Optional[str] = None,
    ) -> list["Conversation"]:
        """대화 히스토리 조회, 최신순."""


class ActivityRepositoryInterface(BaseRepository["Activity", "ActivityCreate"]):

    @abstractmethod
    async def has_responded_to(self, platform: str, post_id: str) -> bool:
        """봇이 이 게시글에 이미 댓글을 달았는지 확인. 중복 방지에 핵심."""

    @abstractmethod
    async def get_daily_counts(self, platform: str, target_date: date) -> "DailyCounts":
        """주어진 날짜와 플랫폼에 대한 댓글, 게시글, 추천 카운트."""

    @abstractmethod
    async def get_by_status(self, status: str, limit: int = 50) -> list["Activity"]:
        """상태별 활동 조회 (pending, approved, posted, failed)."""

    @abstractmethod
    async def update_status(
        self, id: int, status: str, error_message: Optional[str] = None
    ) -> None:
        """활동 상태 갱신. 게시 후 또는 실패 시 사용."""

    @abstractmethod
    async def get_timeline(
        self,
        start: Optional[datetime] = None,
        end: Optional[datetime] = None,
        platform_filter: Optional[str] = None,
        type_filter: Optional[str] = None,
        limit: int = 50,
        offset: int = 0,
    ) -> list["Activity"]:
        """필터가 적용된 활동 타임라인 조회."""


class NotificationRepositoryInterface(BaseRepository["NotificationLog", "NotificationCreate"]):

    @abstractmethod
    async def get_unprocessed(self, platform: str) -> list["NotificationLog"]:
        """아직 응답하지 않은 알림 조회."""

    @abstractmethod
    async def mark_responded(self, id: int, response_activity_id: int) -> None:
        """알림을 응답 활동에 연결."""

    @abstractmethod
    async def get_last_check_time(self, platform: str) -> Optional[datetime]:
        """플랫폼의 가장 최근 알림 타임스탬프 조회."""

    @abstractmethod
    async def exists_by_platform_id(self, platform: str, notification_id: str) -> bool:
        """이 알림이 이미 있는지 확인 (폴링 시 중복 제거)."""


class CollectedInfoRepositoryInterface(BaseRepository["CollectedInfo", "CollectedInfoCreate"]):

    @abstractmethod
    async def search(
        self,
        query: Optional[str] = None,
        category: Optional[str] = None,
        bookmarked_only: bool = False,
        limit: int = 50,
        offset: int = 0,
    ) -> list["CollectedInfo"]:
        """필터가 적용된 수집 정보 검색."""

    @abstractmethod
    async def toggle_bookmark(self, id: int) -> bool:
        """북마크 상태 토글. 새 북마크 상태 반환."""

    @abstractmethod
    async def get_categories(self) -> list[str]:
        """고유 카테고리 값 조회."""


class SettingsRepositoryInterface(ABC):

    @abstractmethod
    async def save_snapshot(self, config_json: str) -> None:
        """히스토리용 config 스냅샷 저장."""

    @abstractmethod
    async def get_latest(self) -> Optional[str]:
        """가장 최근 config 스냅샷 JSON 조회."""

    @abstractmethod
    async def get_history(self, limit: int = 20) -> list["SettingsSnapshot"]:
        """config 변경 히스토리 조회."""
```

### 10.3 Service 인터페이스

```python
class LLMServiceInterface(ABC):

    @abstractmethod
    async def generate(
        self,
        prompt: str,
        system: Optional[str] = None,
        stream: bool = False,
    ) -> str | AsyncIterator[str]:
        """텍스트 생성. stream=True이면 청크의 async iterator 반환."""

    @abstractmethod
    async def get_available_models(self) -> list["OllamaModel"]:
        """설치된 Ollama 모델 목록."""

    @abstractmethod
    async def get_model_info(self, model_name: str) -> "OllamaModelInfo":
        """SYSTEM 프롬프트를 포함한 모델 상세 정보."""

    @abstractmethod
    async def check_health(self) -> bool:
        """Ollama 핑. 응답 시 True."""

    @abstractmethod
    async def switch_model(self, model_name: str) -> None:
        """활성 모델 변경."""


class StrategyEngineInterface(ABC):

    @abstractmethod
    async def evaluate_post(
        self, post: "PlatformPost", platform: str
    ) -> "CommentDecision":
        """게시글에 댓글을 달지 결정."""

    @abstractmethod
    async def generate_comment(
        self, post: "PlatformPost", platform: str
    ) -> "QualityCheckedComment":
        """댓글을 생성하고 품질 체크를 실행."""

    @abstractmethod
    async def generate_reply(
        self,
        notification: "PlatformNotification",
        original_post: "PlatformPost",
        conversation_context: list["PlatformComment"],
    ) -> "QualityCheckedComment":
        """전체 컨텍스트를 가진 알림에 대한 답글 생성."""

    @abstractmethod
    async def generate_post(
        self, topic: str, platform: str
    ) -> "QualityCheckedPost":
        """플랫폼용 새 게시글 생성."""

    @abstractmethod
    async def should_upvote(
        self, post: "PlatformPost", platform: str
    ) -> bool:
        """게시글을 추천할지 결정."""


class SchedulerInterface(ABC):

    @abstractmethod
    async def start(self) -> None:
        """모든 예약된 작업 시작."""

    @abstractmethod
    async def stop(self) -> None:
        """모든 예약된 작업을 그레이스풀하게 중지."""

    @abstractmethod
    def get_state(self) -> "SchedulerState":
        """현재 스케줄러 상태 (실행 중 작업, 다음 실행 시간)."""

    @abstractmethod
    async def reschedule(self, task_name: str, new_interval: int) -> None:
        """런타임에 작업 주기 변경."""

    @abstractmethod
    def is_within_active_hours(self) -> bool:
        """현재 시간이 설정된 활동 시간 내인지 확인."""
```

### 10.4 이벤트 타입 (전체)

```python
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Optional


@dataclass(frozen=True)
class Event:
    """기본 이벤트. 모든 이벤트는 불변."""
    timestamp: datetime = field(default_factory=datetime.utcnow)


@dataclass(frozen=True)
class NewPostDiscoveredEvent(Event):
    platform: str = ""
    post: "PlatformPost" = None  # type: ignore
    matched_keywords: list[str] = field(default_factory=list)


@dataclass(frozen=True)
class CommentPostedEvent(Event):
    platform: str = ""
    activity: "Activity" = None  # type: ignore
    post_id: str = ""


@dataclass(frozen=True)
class PostCreatedEvent(Event):
    platform: str = ""
    activity: "Activity" = None  # type: ignore


@dataclass(frozen=True)
class UpvoteEvent(Event):
    platform: str = ""
    post_id: str = ""


@dataclass(frozen=True)
class NotificationReceivedEvent(Event):
    platform: str = ""
    notification: "PlatformNotification" = None  # type: ignore


@dataclass(frozen=True)
class ConfigChangedEvent(Event):
    section: str = ""
    old_value: Any = None
    new_value: Any = None
    needs_restart: bool = False


@dataclass(frozen=True)
class PlatformErrorEvent(Event):
    platform: str = ""
    error_type: str = ""  # "auth", "rate_limit", "server", "network"
    error_message: str = ""
    http_status: Optional[int] = None


@dataclass(frozen=True)
class EmergencyStopEvent(Event):
    source: str = ""  # "file", "api", "shutdown"


@dataclass(frozen=True)
class HealthCheckEvent(Event):
    results: "HealthCheckResult" = None  # type: ignore


@dataclass(frozen=True)
class LLMRequestStartEvent(Event):
    request_id: str = ""
    prompt_preview: str = ""  # 첫 100자


@dataclass(frozen=True)
class LLMResponseCompleteEvent(Event):
    request_id: str = ""
    token_count: int = 0
    duration_ms: int = 0


@dataclass(frozen=True)
class ApprovalRequestedEvent(Event):
    activity: "Activity" = None  # type: ignore
    content_preview: str = ""


@dataclass(frozen=True)
class ApprovalResolvedEvent(Event):
    activity_id: int = 0
    approved: bool = False
    modified_content: Optional[str] = None


@dataclass(frozen=True)
class VoiceCommandEvent(Event):
    transcript: str = ""
    confidence: float = 0.0


@dataclass(frozen=True)
class BotStatusChangedEvent(Event):
    old_status: str = ""  # "active", "idle", "offline", "stopped"
    new_status: str = ""


@dataclass(frozen=True)
class TaskQueuedEvent(Event):
    platform: str = ""
    action_type: str = ""  # "post", "comment", "upvote"
    queue_position: int = 0


@dataclass(frozen=True)
class TaskCompletedEvent(Event):
    platform: str = ""
    action_type: str = ""
    success: bool = True
    error_message: Optional[str] = None
```

### 10.5 핵심 도메인 모델

```python
from pydantic import BaseModel, Field
from datetime import datetime
from typing import Optional
from enum import Enum


# --- Enum ---

class Platform(str, Enum):
    BOTMADANG = "botmadang"
    MOLTBOOK = "moltbook"


class ActivityType(str, Enum):
    COMMENT = "comment"
    POST = "post"
    REPLY = "reply"
    UPVOTE = "upvote"
    DOWNVOTE = "downvote"
    FOLLOW = "follow"


class ActivityStatus(str, Enum):
    PENDING = "pending"
    APPROVED = "approved"
    POSTED = "posted"
    REJECTED = "rejected"
    FAILED = "failed"


class BotStatus(str, Enum):
    ACTIVE = "active"
    IDLE = "idle"
    OFFLINE = "offline"
    STOPPED = "stopped"


# --- 플랫폼 DTO (플랫폼 간 표준화) ---

class PlatformPost(BaseModel):
    platform: Platform
    post_id: str
    title: str
    content: str
    author: str
    community: str
    url: str
    created_at: datetime
    score: int = 0
    comment_count: int = 0


class PlatformComment(BaseModel):
    platform: Platform
    comment_id: str
    post_id: str
    content: str
    author: str
    parent_comment_id: Optional[str] = None
    created_at: datetime


class PlatformNotification(BaseModel):
    platform: Platform
    notification_id: str
    notification_type: str  # "comment_on_post", "reply_to_comment", "upvote_on_post"
    actor_name: str
    post_id: str
    post_title: str = ""
    comment_id: Optional[str] = None
    content_preview: str = ""
    is_read: bool = False
    created_at: datetime


class PlatformCommunity(BaseModel):
    platform: Platform
    name: str
    display_name: str
    description: str = ""


class PlatformPostResult(BaseModel):
    success: bool
    post_id: Optional[str] = None
    url: Optional[str] = None
    error: Optional[str] = None


class PlatformCommentResult(BaseModel):
    success: bool
    comment_id: Optional[str] = None
    error: Optional[str] = None


class RegistrationResult(BaseModel):
    success: bool
    claim_url: Optional[str] = None
    verification_code: Optional[str] = None
    api_key: Optional[str] = None  # claim 후 채워짐
    error: Optional[str] = None


# --- 전략 DTO ---

class CommentDecision(BaseModel):
    should_comment: bool
    reason: str
    priority: int = 5  # 1=최고
    delay_seconds: int = 0


class QualityCheckedComment(BaseModel):
    content: str
    passed: bool
    issues: list[str] = Field(default_factory=list)
    korean_ratio: Optional[float] = None
    length: int = 0


class QualityCheckedPost(BaseModel):
    title: str
    content: str
    community: str
    passed: bool
    issues: list[str] = Field(default_factory=list)


class DailyCounts(BaseModel):
    comments: int = 0
    posts: int = 0
    upvotes: int = 0
    downvotes: int = 0
    follows: int = 0


class DailyLimits(BaseModel):
    max_comments: int = 20
    max_posts: int = 3
    max_upvotes: int = 30


# --- Rate Limit ---

class RateLimitConfig(BaseModel):
    post_cooldown_seconds: int
    comment_cooldown_seconds: int
    api_calls_per_minute: int
    comments_per_day: Optional[int] = None  # Moltbook 전용


class AcquireResult(BaseModel):
    allowed: bool
    wait_seconds: float = 0.0


# --- 헬스 ---

class ComponentHealth(BaseModel):
    name: str
    status: str  # "ok", "degraded", "error"
    message: str = ""
    latency_ms: Optional[int] = None


class HealthCheckResult(BaseModel):
    status: str  # "healthy", "degraded", "unhealthy"
    checks: list[ComponentHealth]
    uptime_seconds: int
    timestamp: datetime
    vram_usage_mb: Optional[int] = None
    vram_total_mb: Optional[int] = None
    disk_free_gb: Optional[float] = None
```

---

## 핵심 설계 결정 요약

이 문서의 모든 설계를 관통하는 10가지 핵심 결정과 그 근거:

| # | 설계 결정 | 근거 |
|---|----------|------|
| 1 | **하향 전용 의존의 엄격한 레이어 아키텍처** | 스파게티 코드를 방지하고, 각 레이어를 독립적으로 테스트하며, 팀 병렬 개발을 가능하게 한다. |
| 2 | **이벤트 버스를 통한 서비스 디커플링** | 순환 의존을 만들 수 있는 서비스 간 직접 참조를 제거한다. 서비스 추가/삭제가 다른 서비스에 영향을 주지 않는다. |
| 3 | **타입이 지정된 인터페이스 뒤의 Repository 패턴** | 모든 SQL을 격리하여 인메모리 테스트를 가능하게 하고, 데이터베이스 변경 시 영향 범위를 리포지토리 내부로 제한한다. |
| 4 | **Capability enum을 가진 Adapter 패턴** | 플랫폼 차이를 명시적으로 만들어 런타임 에러를 방지하고, 새 플랫폼 추가를 파일 하나 작성으로 줄인다. |
| 5 | **asyncio.Lock + WAL 모드의 SQLite 쓰기 직렬화** | 비동기 FastAPI 환경에서 SQLite 경합을 완전히 제거하면서, 읽기 성능에는 영향을 주지 않는다. |
| 6 | **원자적 acquire를 가진 플랫폼별 Rate Limiter** | TOCTOU 레이스 컨디션을 방지하면서, 플랫폼 간 불필요한 블로킹을 피한다. |
| 7 | **Observable 패턴의 2단계 Config (핫 리로드 / 재시작)** | 안전성(포트 변경은 재시작)과 편의성(키워드 변경은 즉시 반영)을 모두 확보한다. |
| 8 | **우선순위 기반 Task Queue** | Rate Limit이 걸린 작업을 직렬화하면서, 알림 응답 같은 높은 우선순위 작업이 먼저 처리되도록 보장한다. |
| 9 | **13단계 빌드 순서** | 각 단계가 다음 단계의 기반을 제공하도록 설계되어, 어떤 단계에서도 "아직 안 만든 것에 의존"하는 상황이 발생하지 않는다. |
| 10 | **픽스처 기반 API Mock이 포함된 종합적 테스트 전략** | 실제 API 응답을 캡처한 JSON 픽스처로 현실적인 테스트를 보장하고, 단위/통합/에러 시나리오를 모두 커버한다. |

개발자는 섹션 6의 빌드 순서를 따르고, 섹션 10의 인터페이스 정의를 시스템을 연결하는 계약으로 구현해야 한다.
