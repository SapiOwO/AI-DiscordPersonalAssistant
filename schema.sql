CREATE DATABASE IF NOT EXISTS discord_ai CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
USE discord_ai;

DROP TABLE IF EXISTS messages;
CREATE TABLE messages (
  id BIGINT AUTO_INCREMENT PRIMARY KEY,
  bot_id BIGINT NOT NULL,
  guild_id BIGINT NULL,
  guild_name VARCHAR(255) NULL,
  channel_id BIGINT NOT NULL,
  channel_name VARCHAR(255) NULL,
  message_id BIGINT NULL,
  author_id BIGINT NULL,
  username VARCHAR(255) NULL,
  role ENUM('system','user','assistant') NOT NULL,
  content LONGTEXT,
  created_at DATETIME NOT NULL,
  INDEX idx_messages_guild (bot_id, guild_id, id),
  INDEX idx_messages_channel (bot_id, channel_id, id)
) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS profiles (
  user_id BIGINT NOT NULL,
  bot_id BIGINT NOT NULL,
  username VARCHAR(255),
  given_name VARCHAR(255),
  updated_at DATETIME NOT NULL,
  last_imagine_timestamp DATETIME NULL,
  PRIMARY KEY (user_id, bot_id)
) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS guild_settings (
    guild_id BIGINT NOT NULL,
    bot_id BIGINT NOT NULL,
    setting_key VARCHAR(100) NOT NULL,
    setting_value TEXT,
    PRIMARY KEY (guild_id, bot_id, setting_key)
) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS benchmarks (
  id BIGINT AUTO_INCREMENT PRIMARY KEY,
  bot_id BIGINT NOT NULL,
  channel_id BIGINT NOT NULL,
  author_id BIGINT NULL,
  response_time_seconds FLOAT,
  response_chars INT,
  model VARCHAR(255),
  created_at DATETIME NOT NULL
) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS search_queries (
  id BIGINT AUTO_INCREMENT PRIMARY KEY,
  bot_id BIGINT NOT NULL,
  channel_id BIGINT,
  query_key VARCHAR(255) NOT NULL,
  query_text VARCHAR(255),
  first_seen DATETIME NOT NULL,
  last_seen DATETIME NOT NULL,
  hit_count INT DEFAULT 1,
  INDEX idx_search_query_key (bot_id, query_key)
) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS search_documents (
  id BIGINT AUTO_INCREMENT PRIMARY KEY,
  search_query_id BIGINT NOT NULL,
  title VARCHAR(512),
  link VARCHAR(2000),
  link_hash CHAR(64) NOT NULL,
  snippet LONGTEXT,
  source_domain VARCHAR(255),
  fetched_at DATETIME NOT NULL,
  UNIQUE KEY uq_query_linkhash (search_query_id, link_hash)
) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;