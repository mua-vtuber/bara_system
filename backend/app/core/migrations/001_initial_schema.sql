CREATE TABLE IF NOT EXISTS conversations (
    id INTEGER PRIMARY KEY,
    timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
    role TEXT NOT NULL,
    content TEXT NOT NULL,
    platform TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS activities (
    id INTEGER PRIMARY KEY,
    timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
    type TEXT NOT NULL,
    platform TEXT NOT NULL,
    platform_post_id TEXT,
    platform_comment_id TEXT,
    parent_id TEXT,
    url TEXT,
    original_content TEXT,
    bot_response TEXT,
    translated_content TEXT,
    translation_direction TEXT,
    llm_prompt TEXT,
    status TEXT NOT NULL DEFAULT 'pending',
    error_message TEXT
);

CREATE TABLE IF NOT EXISTS collected_info (
    id INTEGER PRIMARY KEY,
    timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
    platform TEXT NOT NULL,
    author TEXT,
    category TEXT,
    title TEXT,
    content TEXT,
    source_url TEXT,
    bookmarked BOOLEAN DEFAULT FALSE,
    tags TEXT
);

CREATE TABLE IF NOT EXISTS settings_history (
    id INTEGER PRIMARY KEY,
    timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
    config_snapshot TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS notification_log (
    id INTEGER PRIMARY KEY,
    timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
    platform TEXT NOT NULL,
    notification_id TEXT NOT NULL,
    notification_type TEXT NOT NULL,
    actor_name TEXT,
    post_id TEXT,
    is_read BOOLEAN DEFAULT FALSE,
    response_activity_id INTEGER,
    FOREIGN KEY (response_activity_id) REFERENCES activities(id)
);

CREATE INDEX IF NOT EXISTS idx_activities_platform_post
    ON activities(platform, platform_post_id);

CREATE INDEX IF NOT EXISTS idx_activities_status
    ON activities(status);

CREATE INDEX IF NOT EXISTS idx_notification_log_platform_read
    ON notification_log(platform, is_read)
