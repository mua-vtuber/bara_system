# Memory System Redesign Plan

## Context

bara_system의 현재 메모리 시스템은 단순한 키워드 매칭 + 벡터 검색 구조로, 봇이 시간이 지나도 "똑똑해지지" 않는다. UMSA(Open-LLM-VTuber)의 아키텍처 + Stanford Generative Agents의 Reflection 메커니즘 + Mem0 스타일 구조화 추출을 결합하여, 봇이 경험을 축적하고 이해를 깊게 하는 메모리 시스템으로 재설계한다.

**핵심 목표**: 봇이 소셜 상호작용을 통해 실제로 학습하고, 관계를 이해하며, 시간이 지날수록 자연스러운 대화를 할 수 있게 한다.

**제약 조건**:
- Ollama 기반 임베딩 유지 (sentence-transformers/torch 추가 없음)
- EventBus 통합 유지
- PromptBuilder 통합 유지
- 기존 데이터 비파괴 마이그레이션

---

## New File Structure

```
backend/app/
  core/
    migrations/
      005_memory_redesign.sql       # NEW: 새 테이블, FTS5, 트리거
    config.py                       # MODIFY: MemoryConfig 섹션 추가
    constants.py                    # MODIFY: 메모리 상수 추가
  models/
    memory.py                       # MODIFY: 새 Pydantic 모델 추가
  repositories/
    memory.py                       # KEEP: 기존 BotMemoryRepository (하위호환)
    collected_info.py               # KEEP: 기존 CollectedInfoRepository (하위호환)
    memory_store.py                 # NEW: 통합 메모리 저장소
  services/
    memory/
      __init__.py                   # NEW: MemoryFacade re-export
      facade.py                     # NEW: 최상위 파사드 (기존 MemoryService 대체)
      retriever.py                  # NEW: 3소스 하이브리드 검색
      extractor.py                  # NEW: LLM 기반 사실 추출
      evolver.py                    # NEW: 메모리 진화 (merge/prune)
      reflector.py                  # NEW: Reflection 엔진
      context_assembler.py          # NEW: 토큰 예산 기반 컨텍스트 조립
      token_counter.py              # NEW: CJK 인식 토큰 추정
      scoring.py                    # NEW: Stanford 3-factor 스코링
    embedding.py                    # KEEP: 변경 없음
    auto_capture.py                 # MODIFY: extractor 콜백 추가
    prompt_builder.py               # MODIFY: ContextAssembler 연동
    memory.py                       # MODIFY: MemoryFacade 위임 shim
  main.py                           # MODIFY: 새 서비스 초기화 및 연결
```

---

## Phase 1: Foundation

### 1-1. DB Migration (`005_memory_redesign.sql`)

```sql
-- knowledge_nodes: 원자적 사실, 선호, 트리플, 인사이트, 에피소드
CREATE TABLE IF NOT EXISTS knowledge_nodes (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    content TEXT NOT NULL,
    memory_type TEXT NOT NULL DEFAULT 'fact',
    source_type TEXT NOT NULL DEFAULT 'auto_capture',
    importance REAL NOT NULL DEFAULT 0.5,
    confidence REAL NOT NULL DEFAULT 0.7,
    platform TEXT DEFAULT '',
    author TEXT DEFAULT '',
    created_at TEXT NOT NULL DEFAULT (datetime('now')),
    last_accessed_at TEXT NOT NULL DEFAULT (datetime('now')),
    access_count INTEGER NOT NULL DEFAULT 0,
    embedding BLOB DEFAULT NULL,
    metadata_json TEXT DEFAULT '{}'
);

-- FTS5 전문검색 (Korean unicode61 tokenizer)
CREATE VIRTUAL TABLE IF NOT EXISTS knowledge_nodes_fts USING fts5(
    content, content='knowledge_nodes', content_rowid='id', tokenize='unicode61'
);

-- FTS5 자동 동기화 트리거
CREATE TRIGGER IF NOT EXISTS kn_fts_insert AFTER INSERT ON knowledge_nodes BEGIN
    INSERT INTO knowledge_nodes_fts(rowid, content) VALUES (new.id, new.content);
END;
CREATE TRIGGER IF NOT EXISTS kn_fts_delete AFTER DELETE ON knowledge_nodes BEGIN
    INSERT INTO knowledge_nodes_fts(knowledge_nodes_fts, rowid, content)
    VALUES ('delete', old.id, old.content);
END;
CREATE TRIGGER IF NOT EXISTS kn_fts_update AFTER UPDATE OF content ON knowledge_nodes BEGIN
    INSERT INTO knowledge_nodes_fts(knowledge_nodes_fts, rowid, content)
    VALUES ('delete', old.id, old.content);
    INSERT INTO knowledge_nodes_fts(rowid, content) VALUES (new.id, new.content);
END;

-- knowledge_edges: 노드 간 관계 그래프
CREATE TABLE IF NOT EXISTS knowledge_edges (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    source_id INTEGER NOT NULL,
    target_id INTEGER NOT NULL,
    relation TEXT NOT NULL DEFAULT 'related_to',
    weight REAL NOT NULL DEFAULT 1.0,
    created_at TEXT NOT NULL DEFAULT (datetime('now')),
    FOREIGN KEY (source_id) REFERENCES knowledge_nodes(id) ON DELETE CASCADE,
    FOREIGN KEY (target_id) REFERENCES knowledge_nodes(id) ON DELETE CASCADE
);

-- entity_profiles: 엔티티별 관계 프로필
CREATE TABLE IF NOT EXISTS entity_profiles (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    platform TEXT NOT NULL,
    entity_name TEXT NOT NULL,
    entity_type TEXT NOT NULL DEFAULT 'bot',
    display_name TEXT DEFAULT '',
    summary TEXT DEFAULT '',
    interests_json TEXT DEFAULT '[]',
    personality_notes TEXT DEFAULT '',
    first_seen_at TEXT NOT NULL DEFAULT (datetime('now')),
    last_interaction_at TEXT NOT NULL DEFAULT (datetime('now')),
    interaction_count INTEGER NOT NULL DEFAULT 0,
    sentiment TEXT NOT NULL DEFAULT 'neutral',
    sentiment_score REAL NOT NULL DEFAULT 0.0,
    trust_level REAL NOT NULL DEFAULT 0.5,
    embedding BLOB DEFAULT NULL,
    UNIQUE(platform, entity_name)
);

-- sentiment_history: 감정 궤적 추적
CREATE TABLE IF NOT EXISTS sentiment_history (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    entity_profile_id INTEGER NOT NULL,
    timestamp TEXT NOT NULL DEFAULT (datetime('now')),
    sentiment_label TEXT NOT NULL DEFAULT 'neutral',
    sentiment_score REAL NOT NULL DEFAULT 0.0,
    context TEXT DEFAULT '',
    FOREIGN KEY (entity_profile_id) REFERENCES entity_profiles(id) ON DELETE CASCADE
);

-- consolidation_log: 메모리 진화 기록
CREATE TABLE IF NOT EXISTS consolidation_log (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    timestamp TEXT NOT NULL DEFAULT (datetime('now')),
    operation TEXT NOT NULL,
    details_json TEXT DEFAULT '{}',
    nodes_affected INTEGER DEFAULT 0
);

-- memory_sessions: 에피소드 메모리용 세션 추적
CREATE TABLE IF NOT EXISTS memory_sessions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    platform TEXT NOT NULL DEFAULT 'chat',
    started_at TEXT NOT NULL DEFAULT (datetime('now')),
    ended_at TEXT DEFAULT NULL,
    turn_count INTEGER NOT NULL DEFAULT 0,
    summary TEXT DEFAULT '',
    topic TEXT DEFAULT ''
);

-- 인덱스
CREATE INDEX IF NOT EXISTS idx_kn_memory_type ON knowledge_nodes(memory_type);
CREATE INDEX IF NOT EXISTS idx_kn_author ON knowledge_nodes(author);
CREATE INDEX IF NOT EXISTS idx_kn_importance ON knowledge_nodes(importance DESC);
CREATE INDEX IF NOT EXISTS idx_kn_last_accessed ON knowledge_nodes(last_accessed_at);
CREATE INDEX IF NOT EXISTS idx_ke_source ON knowledge_edges(source_id);
CREATE INDEX IF NOT EXISTS idx_ke_target ON knowledge_edges(target_id);
CREATE UNIQUE INDEX IF NOT EXISTS idx_ke_pair ON knowledge_edges(source_id, target_id, relation);
CREATE INDEX IF NOT EXISTS idx_ep_platform ON entity_profiles(platform, entity_name);
CREATE INDEX IF NOT EXISTS idx_ep_interaction ON entity_profiles(interaction_count DESC);
CREATE INDEX IF NOT EXISTS idx_sh_entity ON sentiment_history(entity_profile_id, timestamp);
CREATE INDEX IF NOT EXISTS idx_ms_platform ON memory_sessions(platform, started_at);
```

### 1-2. New Pydantic Models (`models/memory.py` 추가)

기존 `BotMemory`, `BotMemoryCreate` 유지하고 아래 추가:

- `MemoryType(str, Enum)`: fact, preference, triple, insight, episode
- `SourceType(str, Enum)`: auto_capture, llm_extract, reflection, user_explicit
- `KnowledgeNodeCreate`, `KnowledgeNode`: 지식 노드 CRUD 모델
- `KnowledgeEdge`: 그래프 엣지 모델
- `EntityProfileCreate`, `EntityProfile`: 엔티티 프로필 모델
- `RetrievalResult`: 검색 결과 (node + score + source)
- `ExtractionResult`: LLM 추출 결과 (content + type + importance)

### 1-3. Unified Repository (`repositories/memory_store.py`)

`MemoryStoreRepository(BaseRepository)` - 모든 새 테이블을 관리하는 단일 저장소:

**Knowledge Nodes**: `add_node`, `get_node`, `get_nodes_by_ids`, `touch_node`, `update_node_importance`, `delete_node`, `get_embedding_candidates`, `get_nodes_for_pruning`, `get_nodes_for_merging`

**FTS5 Search**: `fts_search(query, limit)` → `(node_id, rank)` 쌍. FTS5 특수문자 sanitize 포함.

**Knowledge Edges**: `add_edge`, `get_neighbors`, `get_connected_nodes` (BFS 그래프 순회)

**Entity Profiles**: `upsert_entity`, `get_entity`, `increment_interaction`, `update_entity_summary`, `update_entity_sentiment`, `get_frequent_entities`

**Sentiment History**: `add_sentiment_entry`, `get_sentiment_trajectory`

**Consolidation**: `log_consolidation`

**Sessions**: `start_session`, `end_session`, `increment_session_turns`

### 1-4. Config & Constants

`config.py`에 `MemoryConfig` 추가:
```python
class MemoryConfig(BaseModel):
    extraction_enabled: bool = True
    extraction_min_importance: float = 0.3
    reflection_enabled: bool = True
    reflection_threshold: int = 20
    evolution_enabled: bool = True
    evolution_interval_hours: int = 6
    merge_similarity_threshold: float = 0.85
    prune_importance_threshold: float = 0.2
    recency_half_life_days: float = 30.0
    context_total_budget: int = 4096
    retrieval_limit: int = 10
    fts_enabled: bool = True
    graph_max_hops: int = 2
```

`constants.py`에 해당 기본값 상수 추가.

### 1-5. Utilities

- `services/memory/token_counter.py`: CJK 인식 토큰 추정 (tiktoken 없이, Ollama 모델용 휴리스틱)
- `services/memory/scoring.py`: Stanford 3-factor 스코링 함수들
  - `compute_recency(last_accessed_at)` → exponential decay (half-life 30일)
  - `compute_combined_score(recency, relevance, importance)` → 가중합
  - 가중치: recency 0.3, relevance 0.5, importance 0.2

---

## Phase 2: Hybrid Retriever (`services/memory/retriever.py`)

`HybridRetriever` - 3소스 하이브리드 검색:

1. **Vector Search**: 쿼리 임베딩 → `get_embedding_candidates()` → cosine similarity → 3-factor 스코어
2. **FTS5 Search**: 쿼리 sanitize → `fts_search()` → rank 정규화 → 3-factor 스코어
3. **Graph Expansion**: 상위 vector+FTS 결과 seed → `get_connected_nodes()` 1-2홉 → edge weight를 relevance로 사용

**결과 융합**: 동일 노드가 여러 소스에서 발견되면 가중 평균 (vector 0.5, fts 0.3, graph 0.2). 접근된 노드는 `touch_node()`로 recency 갱신.

기존 `EmbeddingService` 재사용 - 변경 없음.

---

## Phase 3: Memory Extractor (`services/memory/extractor.py`)

`MemoryExtractor` - LLM 기반 구조화 사실 추출:

- 봇 상호작용에서 원자적 사실/선호/트리플을 추출
- 한국어 인식 추출 프롬프트 (JSON 출력 요청)
- 중요도/신뢰도 임계값 필터링
- 임베딩 유사도로 중복 검사
- `knowledge_nodes`에 저장 + 엔티티 프로필 연결 edge 생성

**이중 경로**: `AutoCaptureService`의 한국어 regex → 빠르고 무비용. `MemoryExtractor`의 LLM → 느리지만 구조화된 추출. 둘 다 실행, 양쪽 모두 `knowledge_nodes`에 저장.

`auto_capture.py` 수정: `set_extractor_callback()` 추가하여 regex 캡처 후 LLM 추출도 트리거.

---

## Phase 4: Evolution & Reflection

### 4-1. MemoryEvolver (`services/memory/evolver.py`)

- **Merge**: cosine similarity > 0.85인 노드 쌍 → 높은 importance 유지, `merged_from` edge 생성, 낮은 쪽 삭제. 후보 500개 상한 (O(n^2) 방지)
- **Prune**: importance ≤ 0.2 AND access_count == 0 AND age > 60일(half-life 2배) → 삭제
- 스케줄러로 6시간마다 실행

### 4-2. ReflectionEngine (`services/memory/reflector.py`)

봇을 "똑똑하게" 만드는 핵심 컴포넌트:

- 마지막 reflection 이후 N개(기본 20) 새 노드 축적 시 트리거
- 최근 노드를 엔티티/토픽별로 그룹핑
- LLM에게 그룹별 인사이트 생성 요청 (한국어)
- 인사이트를 `memory_type='insight'`로 저장
- source 노드들과 `derived_from` edge 생성
- 엔티티 프로필의 summary 갱신

**예시 출력**: "UserA는 주로 AI 윤리에 관심이 많고, 기술적 토론을 선호한다. 최근 DeFi 관련 질문이 늘어나는 추세."

---

## Phase 5: Context Assembly & Integration

### 5-1. ContextAssembler (`services/memory/context_assembler.py`)

토큰 예산 기반 프롬프트 조립:

| 컴포넌트 | 예산 비율 | 설명 |
|---------|----------|------|
| system_prompt | 15% | 성격/페르소나 |
| entity_profile | 10% | 대화 상대 프로필 |
| memories | 20% | 검색된 관련 기억 |
| few_shot | 5% | 응답 예시 |
| user_content | 40% | 포스트/대화 내용 |
| response_reserve | 10% | 응답 생성용 여유 |

비어있는 컴포넌트의 예산은 다른 컴포넌트에 재분배.

### 5-2. MemoryFacade (`services/memory/facade.py`)

모든 서브시스템을 통합하는 최상위 파사드:

**하위호환 API** (기존 MemoryService 시그니처 유지):
- `remember_post()`, `remember_interaction()`, `get_context_for_post()`, `recall_related()`, `recall_bot()`, `get_frequent_contacts()`

**새 API**:
- `retrieve_memories()`: 하이브리드 검색
- `extract_and_store()`: LLM 추출 + 저장
- `get_entity_profile()`: 엔티티 프로필 조회
- `run_maintenance()`: evolution + reflection 실행

**이벤트 핸들러**:
- `on_new_post()`, `on_comment_posted()`, `on_notification()`, `on_bot_response()`

### 5-3. 기존 파일 수정

**`services/memory.py`**: MemoryFacade 위임 shim으로 변환. `_facade` 속성이 설정되면 위임, 아니면 기존 로직 유지.

**`services/prompt_builder.py`**: `build_comment_prompt()`에 `memory_context: str = ""`, `entity_context: str = ""` 파라미터 추가. 제공되면 기존 memories/related_info 대신 사용.

**`services/auto_capture.py`**: `set_extractor_callback()` 메서드 추가. regex 캡처 후 LLM 추출 콜백 트리거.

**`main.py`**: 새 서비스 초기화, EventBus 구독, 스케줄러 등록, app.state 바인딩.

---

## Phase 6: Data Migration

비파괴적 마이그레이션 - 기존 테이블 유지:

- `bot_memory` → `entity_profiles` (interaction_count, topics, sentiment 보존)
- `collected_info` → `knowledge_nodes` (임베딩, 카테고리 보존)
- `good_examples` → `knowledge_nodes` (memory_type='episode')
- `consolidation_log`에 마이그레이션 기록 → 재실행 방지

첫 실행 시 백그라운드로 실행, 이후 자동 스킵.

---

## Critical Files

| 파일 | 작업 | 중요도 |
|------|------|--------|
| `core/migrations/005_memory_redesign.sql` | NEW | 전체 스키마 기반 |
| `repositories/memory_store.py` | NEW | 데이터 접근 계층 |
| `services/memory/retriever.py` | NEW | 검색 품질 핵심 |
| `services/memory/extractor.py` | NEW | 지식 축적 핵심 |
| `services/memory/reflector.py` | NEW | "똑똑해짐" 핵심 |
| `services/memory/facade.py` | NEW | 통합 조정자 |
| `services/memory/context_assembler.py` | NEW | 프롬프트 품질 |
| `services/memory/scoring.py` | NEW | 검색 랭킹 |
| `services/memory/token_counter.py` | NEW | 토큰 예산 관리 |
| `models/memory.py` | MODIFY | 새 데이터 모델 |
| `core/config.py` | MODIFY | MemoryConfig 추가 |
| `core/constants.py` | MODIFY | 메모리 상수 추가 |
| `services/prompt_builder.py` | MODIFY | 조립된 컨텍스트 수용 |
| `services/auto_capture.py` | MODIFY | extractor 콜백 |
| `services/memory.py` | MODIFY | facade 위임 shim |
| `main.py` | MODIFY | 전체 와이어링 |

---

## Verification

1. **Migration**: `python -c "from app.core.database import Database; ..."` 실행 후 새 테이블 생성 확인
2. **Repository CRUD**: knowledge_nodes INSERT/SELECT/UPDATE/DELETE + FTS5 검색 테스트
3. **Vector + FTS5 + Graph 검색**: 테스트 데이터 삽입 후 3소스 하이브리드 검색 결과 확인
4. **LLM Extraction**: 샘플 대화 텍스트 → 구조화 추출 결과 확인
5. **Evolution**: 유사 노드 merge, stale 노드 prune 확인
6. **Reflection**: 20개 노드 축적 후 인사이트 생성 확인
7. **End-to-end**: EventBus 이벤트 발행 → 추출 → 저장 → 검색 → 프롬프트 조립 → LLM 응답 생성
8. **Backward compat**: 기존 `MemoryService` API 호출이 정상 동작하는지 확인
9. **Legacy migration**: 기존 bot_memory, collected_info 데이터가 새 테이블로 정상 이관되는지 확인
