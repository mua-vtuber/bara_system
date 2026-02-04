-- Good examples: store high-engagement bot responses for few-shot learning
CREATE TABLE IF NOT EXISTS good_examples (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    created_at TEXT NOT NULL DEFAULT (datetime('now')),
    platform TEXT NOT NULL,
    action_type TEXT NOT NULL DEFAULT 'comment',
    context_title TEXT DEFAULT '',
    context_content TEXT DEFAULT '',
    bot_response TEXT NOT NULL,
    engagement_score REAL DEFAULT 0.0,
    reply_count INTEGER DEFAULT 0,
    upvote_count INTEGER DEFAULT 0,
    activity_id INTEGER,
    post_id TEXT DEFAULT '',
    embedding BLOB DEFAULT NULL
);
