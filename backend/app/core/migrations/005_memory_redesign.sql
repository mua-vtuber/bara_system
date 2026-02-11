-- Memory system redesign: knowledge graph, entity profiles, reflection support
-- Adds knowledge_nodes (with FTS5), knowledge_edges, entity_profiles,
-- sentiment_history, consolidation_log, and memory_sessions tables.

-- knowledge_nodes: atomic facts, preferences, triples, insights, episodes
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

-- FTS5 full-text search (unicode61 tokenizer for Korean support)
CREATE VIRTUAL TABLE IF NOT EXISTS knowledge_nodes_fts USING fts5(
    content, content='knowledge_nodes', content_rowid='id', tokenize='unicode61'
);

-- FTS5 auto-sync triggers
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

-- knowledge_edges: relationship graph between nodes
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

-- entity_profiles: per-entity relationship profiles
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

-- sentiment_history: sentiment trajectory tracking
CREATE TABLE IF NOT EXISTS sentiment_history (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    entity_profile_id INTEGER NOT NULL,
    timestamp TEXT NOT NULL DEFAULT (datetime('now')),
    sentiment_label TEXT NOT NULL DEFAULT 'neutral',
    sentiment_score REAL NOT NULL DEFAULT 0.0,
    context TEXT DEFAULT '',
    FOREIGN KEY (entity_profile_id) REFERENCES entity_profiles(id) ON DELETE CASCADE
);

-- consolidation_log: memory evolution audit trail
CREATE TABLE IF NOT EXISTS consolidation_log (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    timestamp TEXT NOT NULL DEFAULT (datetime('now')),
    operation TEXT NOT NULL,
    details_json TEXT DEFAULT '{}',
    nodes_affected INTEGER DEFAULT 0
);

-- memory_sessions: episode memory session tracking
CREATE TABLE IF NOT EXISTS memory_sessions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    platform TEXT NOT NULL DEFAULT 'chat',
    started_at TEXT NOT NULL DEFAULT (datetime('now')),
    ended_at TEXT DEFAULT NULL,
    turn_count INTEGER NOT NULL DEFAULT 0,
    summary TEXT DEFAULT '',
    topic TEXT DEFAULT ''
);

-- Indexes for knowledge_nodes
CREATE INDEX IF NOT EXISTS idx_kn_memory_type ON knowledge_nodes(memory_type);
CREATE INDEX IF NOT EXISTS idx_kn_author ON knowledge_nodes(author);
CREATE INDEX IF NOT EXISTS idx_kn_importance ON knowledge_nodes(importance DESC);
CREATE INDEX IF NOT EXISTS idx_kn_last_accessed ON knowledge_nodes(last_accessed_at);
CREATE INDEX IF NOT EXISTS idx_kn_source_type ON knowledge_nodes(source_type);
CREATE INDEX IF NOT EXISTS idx_kn_platform ON knowledge_nodes(platform);

-- Indexes for knowledge_edges
CREATE INDEX IF NOT EXISTS idx_ke_source ON knowledge_edges(source_id);
CREATE INDEX IF NOT EXISTS idx_ke_target ON knowledge_edges(target_id);
CREATE UNIQUE INDEX IF NOT EXISTS idx_ke_pair ON knowledge_edges(source_id, target_id, relation);

-- Indexes for entity_profiles
CREATE INDEX IF NOT EXISTS idx_ep_platform ON entity_profiles(platform, entity_name);
CREATE INDEX IF NOT EXISTS idx_ep_interaction ON entity_profiles(interaction_count DESC);

-- Indexes for sentiment_history
CREATE INDEX IF NOT EXISTS idx_sh_entity ON sentiment_history(entity_profile_id, timestamp);

-- Indexes for memory_sessions
CREATE INDEX IF NOT EXISTS idx_ms_platform ON memory_sessions(platform, started_at);
