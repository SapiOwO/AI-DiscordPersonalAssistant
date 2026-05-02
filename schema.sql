-- Enable pgvector extension
CREATE EXTENSION IF NOT EXISTS vector;

-- ============================================================
-- Table: messages (Unified Chat Logs + Vector Memory)
-- ============================================================
CREATE TABLE IF NOT EXISTS messages (
    id BIGSERIAL PRIMARY KEY,
    bot_id BIGINT NOT NULL,
    guild_id BIGINT,
    guild_name VARCHAR(255),
    channel_id BIGINT NOT NULL,
    channel_name VARCHAR(255),
    message_id BIGINT,
    author_id BIGINT,
    username VARCHAR(255),
    role VARCHAR(20) NOT NULL CHECK (role IN ('system', 'user', 'assistant')),
    content TEXT,
    embedding vector(768),  -- nomic-embed-text dimensions
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
);

-- Fast lookups by channel (conversation history)
CREATE INDEX IF NOT EXISTS idx_messages_channel
    ON messages (bot_id, channel_id, id);

-- Fast lookups by guild (omnipresent memory)
CREATE INDEX IF NOT EXISTS idx_messages_guild
    ON messages (bot_id, guild_id, id);

-- Fast lookups by author (for RAG scoped to a user)
CREATE INDEX IF NOT EXISTS idx_messages_author
    ON messages (author_id, id);

-- HNSW index for fast vector similarity search (only on rows with embeddings)
CREATE INDEX IF NOT EXISTS idx_messages_embedding_hnsw
    ON messages USING hnsw (embedding vector_cosine_ops);

-- ============================================================
-- Table: profiles
-- ============================================================
CREATE TABLE IF NOT EXISTS profiles (
    user_id BIGINT NOT NULL,
    bot_id BIGINT NOT NULL,
    username VARCHAR(255),
    given_name VARCHAR(255),
    updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    last_imagine_timestamp TIMESTAMP DEFAULT NULL,
    PRIMARY KEY (user_id, bot_id)
);

-- ============================================================
-- Table: guild_settings
-- ============================================================
CREATE TABLE IF NOT EXISTS guild_settings (
    guild_id BIGINT PRIMARY KEY,
    persona_enabled BOOLEAN DEFAULT FALSE,
    persona_text TEXT,
    show_footer_info BOOLEAN DEFAULT FALSE
);

-- ============================================================
-- Table: dynamic_settings
-- ============================================================
CREATE TABLE IF NOT EXISTS dynamic_settings (
    channel_id BIGINT PRIMARY KEY,
    guild_id BIGINT,
    enable_context BOOLEAN DEFAULT FALSE,
    enable_afk BOOLEAN DEFAULT FALSE,
    max_pings INT DEFAULT 5
);

-- ============================================================
-- Table: benchmarks
-- ============================================================
CREATE TABLE IF NOT EXISTS benchmarks (
    id BIGSERIAL PRIMARY KEY,
    bot_id BIGINT NOT NULL,
    channel_id BIGINT NOT NULL,
    author_id BIGINT,
    response_time_seconds FLOAT,
    response_chars INT,
    model VARCHAR(255),
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
);

-- ============================================================
-- CLEANUP: Drop legacy vector_memories table if it exists
-- ============================================================
DROP TABLE IF EXISTS vector_memories;