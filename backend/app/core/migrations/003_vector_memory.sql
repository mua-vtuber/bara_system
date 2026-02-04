-- Vector memory: add embedding columns for semantic search
ALTER TABLE collected_info ADD COLUMN embedding BLOB DEFAULT NULL;
ALTER TABLE bot_memory ADD COLUMN embedding BLOB DEFAULT NULL;
