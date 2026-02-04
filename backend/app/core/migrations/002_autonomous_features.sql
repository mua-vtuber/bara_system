-- Migration 002: Autonomous bot features - memory and missions
-- Bot memory: track other bots/users the bot has interacted with
CREATE TABLE IF NOT EXISTS bot_memory (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    platform TEXT NOT NULL,
    entity_name TEXT NOT NULL,
    entity_type TEXT DEFAULT 'bot',
    first_seen_at TEXT NOT NULL DEFAULT (datetime('now')),
    last_interaction_at TEXT NOT NULL DEFAULT (datetime('now')),
    interaction_count INTEGER DEFAULT 0,
    topics TEXT DEFAULT '[]',
    relationship_notes TEXT DEFAULT '',
    sentiment TEXT DEFAULT 'neutral',
    UNIQUE(platform, entity_name)
);

CREATE INDEX IF NOT EXISTS idx_bot_memory_platform ON bot_memory(platform, entity_name);
CREATE INDEX IF NOT EXISTS idx_bot_memory_sentiment ON bot_memory(sentiment);

-- Missions: user-directed information collection tasks
CREATE TABLE IF NOT EXISTS missions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    created_at TEXT NOT NULL DEFAULT (datetime('now')),
    topic TEXT NOT NULL,
    question_hint TEXT DEFAULT '',
    urgency TEXT DEFAULT 'normal',
    status TEXT DEFAULT 'pending',
    target_platform TEXT DEFAULT '',
    target_community TEXT DEFAULT '',
    warmup_count INTEGER DEFAULT 0,
    warmup_target INTEGER DEFAULT 3,
    post_id TEXT DEFAULT '',
    post_platform TEXT DEFAULT '',
    collected_responses TEXT DEFAULT '[]',
    summary TEXT DEFAULT '',
    completed_at TEXT,
    user_notes TEXT DEFAULT ''
);

CREATE INDEX IF NOT EXISTS idx_missions_status ON missions(status);
CREATE INDEX IF NOT EXISTS idx_missions_created ON missions(created_at);
