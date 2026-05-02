import os
import json
import logging
from datetime import datetime
from typing import Optional, List, Dict, Any

import asyncpg
from dotenv import load_dotenv

load_dotenv()
logger = logging.getLogger("db")

DB_HOST = os.getenv("DB_HOST", "127.0.0.1")
DB_PORT = os.getenv("DB_PORT", "5432")
DB_USER = os.getenv("DB_USER", "postgres")
DB_PASSWORD = os.getenv("DB_PASS", "admin")
DB_NAME = os.getenv("DB_NAME", "discord_ai")

db_pool: Optional[asyncpg.Pool] = None

DEFAULT_GUILD_SETTINGS = {
    "persona_enabled": False,
    "persona_text": os.getenv("DEFAULT_PERSONA", "You are a helpful AI assistant."),
    "show_footer_info": False,
}


async def init_db():
    global db_pool
    try:
        db_pool = await asyncpg.create_pool(
            host=DB_HOST,
            port=DB_PORT,
            user=DB_USER,
            password=DB_PASSWORD,
            database=DB_NAME,
            min_size=1,
            max_size=10,
        )
        logger.info("PostgreSQL pool initialized successfully.")
    except Exception as e:
        logger.error(f"Failed to initialize PostgreSQL: {e}")
        raise


# ─────────────────────────────────────────────
#  Dynamic Settings
# ─────────────────────────────────────────────

async def get_all_dynamic_configs() -> Dict[int, Dict]:
    if db_pool is None:
        return {}
    async with db_pool.acquire() as conn:
        rows = await conn.fetch("SELECT * FROM dynamic_settings")
        return {row["channel_id"]: dict(row) for row in rows}


async def get_dynamic_config(channel_id: int) -> Optional[Dict]:
    if db_pool is None:
        return None
    async with db_pool.acquire() as conn:
        row = await conn.fetchrow("SELECT * FROM dynamic_settings WHERE channel_id = $1", channel_id)
        return dict(row) if row else None


async def set_dynamic_config(channel_id: int, guild_id: Optional[int], enable_context: bool, enable_afk: bool, max_pings: int):
    if db_pool is None:
        return
    async with db_pool.acquire() as conn:
        await conn.execute("""
            INSERT INTO dynamic_settings (channel_id, guild_id, enable_context, enable_afk, max_pings)
            VALUES ($1, $2, $3, $4, $5)
            ON CONFLICT (channel_id) DO UPDATE SET
                guild_id = EXCLUDED.guild_id,
                enable_context = EXCLUDED.enable_context,
                enable_afk = EXCLUDED.enable_afk,
                max_pings = EXCLUDED.max_pings
        """, channel_id, guild_id, enable_context, enable_afk, max_pings)


async def remove_dynamic_config(channel_id: int):
    if db_pool is None:
        return
    async with db_pool.acquire() as conn:
        await conn.execute("DELETE FROM dynamic_settings WHERE channel_id=$1", channel_id)


# ─────────────────────────────────────────────
#  Guild Settings
# ─────────────────────────────────────────────

async def get_guild_settings(guild_id: int) -> Dict[str, Any]:
    if db_pool is None:
        return DEFAULT_GUILD_SETTINGS.copy()
    async with db_pool.acquire() as conn:
        row = await conn.fetchrow("SELECT * FROM guild_settings WHERE guild_id = $1", guild_id)
        return dict(row) if row else DEFAULT_GUILD_SETTINGS.copy()


async def update_guild_settings(guild_id: int, persona_enabled: bool, persona_text: str, show_footer_info: bool):
    if db_pool is None:
        return
    async with db_pool.acquire() as conn:
        await conn.execute("""
            INSERT INTO guild_settings (guild_id, persona_enabled, persona_text, show_footer_info)
            VALUES ($1, $2, $3, $4)
            ON CONFLICT (guild_id) DO UPDATE SET
                persona_enabled = EXCLUDED.persona_enabled,
                persona_text = EXCLUDED.persona_text,
                show_footer_info = EXCLUDED.show_footer_info
        """, guild_id, persona_enabled, persona_text, show_footer_info)


# ─────────────────────────────────────────────
#  Profiles
# ─────────────────────────────────────────────

async def get_profile(user_id: int, bot_id: int) -> Optional[Dict]:
    if db_pool is None:
        return None
    async with db_pool.acquire() as conn:
        row = await conn.fetchrow("SELECT * FROM profiles WHERE user_id = $1 AND bot_id = $2", user_id, bot_id)
        return dict(row) if row else None


async def save_profile(user_id: int, bot_id: int, username: str, given_name: str):
    if db_pool is None:
        return
    async with db_pool.acquire() as conn:
        await conn.execute("""
            INSERT INTO profiles (user_id, bot_id, username, given_name)
            VALUES ($1, $2, $3, $4)
            ON CONFLICT (user_id, bot_id) DO UPDATE SET
                username = EXCLUDED.username,
                given_name = EXCLUDED.given_name,
                updated_at = CURRENT_TIMESTAMP
        """, user_id, bot_id, username, given_name)


async def update_profile_last_imagine(user_id: int, bot_id: int):
    if db_pool is None:
        return
    async with db_pool.acquire() as conn:
        await conn.execute("""
            UPDATE profiles SET last_imagine_timestamp = CURRENT_TIMESTAMP
            WHERE user_id = $1 AND bot_id = $2
        """, user_id, bot_id)


# ─────────────────────────────────────────────
#  Messages  (Unified chat log + vector memory)
# ─────────────────────────────────────────────

async def save_message(
    bot_id: int,
    guild_id: Optional[int],
    guild_name: Optional[str],
    channel_id: int,
    channel_name: Optional[str],
    message_id: int,
    author_id: int,
    username: str,
    role: str,
    content: str,
) -> Optional[int]:
    """Save a message and return the database row ID."""
    if db_pool is None:
        return None
    async with db_pool.acquire() as conn:
        row = await conn.fetchrow("""
            INSERT INTO messages
                (bot_id, guild_id, guild_name, channel_id, channel_name,
                 message_id, author_id, username, role, content)
            VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10)
            RETURNING id
        """, bot_id, guild_id, guild_name, channel_id, channel_name,
             message_id, author_id, username, role, content)
        return row["id"] if row else None


async def update_message_content(row_id: int, new_content: str):
    """Update the text content of an existing message row."""
    if db_pool is None or row_id is None:
        return
    async with db_pool.acquire() as conn:
        await conn.execute(
            "UPDATE messages SET content = $1 WHERE id = $2",
            new_content, row_id,
        )


async def update_message_embedding(row_id: int, embedding: list):
    """Write a pre-computed embedding vector onto an existing message row."""
    if db_pool is None or row_id is None:
        return
    async with db_pool.acquire() as conn:
        await conn.execute(
            "UPDATE messages SET embedding = $1::vector WHERE id = $2",
            json.dumps(embedding), row_id,
        )


async def vector_search_messages(
    context_id: int,
    guild_id: Optional[int],
    embedding: list,
    n_results: int = 3,
) -> List[Dict]:
    """Find semantically similar messages in the current conversational scope."""
    if db_pool is None:
        return []
    async with db_pool.acquire() as conn:
        if guild_id:
            # Omnipresent memory: search the entire guild
            rows = await conn.fetch("""
                SELECT content, role, username, created_at,
                       embedding <=> $1::vector AS distance
                FROM messages
                WHERE guild_id = $2
                  AND embedding IS NOT NULL
                ORDER BY embedding <=> $1::vector
                LIMIT $3
            """, json.dumps(embedding), guild_id, n_results)
        else:
            # Channel-scoped memory
            rows = await conn.fetch("""
                SELECT content, role, username, created_at,
                       embedding <=> $1::vector AS distance
                FROM messages
                WHERE channel_id = $2
                  AND embedding IS NOT NULL
                ORDER BY embedding <=> $1::vector
                LIMIT $3
            """, json.dumps(embedding), context_id, n_results)
            
        return [dict(r) for r in rows]


# ─────────────────────────────────────────────
#  Conversation History
# ─────────────────────────────────────────────

async def load_conversation_context(
    bot_id: int,
    channel_id: int,
    limit: int = 10,
    guild_id: Optional[int] = None,
) -> List[Dict]:
    if db_pool is None:
        return []
    async with db_pool.acquire() as conn:
        if guild_id:
            rows = await conn.fetch("""
                SELECT role, content, username, created_at, message_id, author_id
                FROM messages
                WHERE bot_id = $1 AND guild_id = $2
                ORDER BY id DESC LIMIT $3
            """, bot_id, guild_id, limit)
        else:
            rows = await conn.fetch("""
                SELECT role, content, username, created_at, message_id, author_id
                FROM messages
                WHERE bot_id = $1 AND channel_id = $2
                ORDER BY id DESC LIMIT $3
            """, bot_id, channel_id, limit)

        return [
            {
                "role": r["role"],
                "content": r["content"],
                "username": r["username"],
                "created_at": r["created_at"],
                "message_id": r["message_id"],
                "author_id": r["author_id"],
                "author_name": r["username"],
            }
            for r in reversed(rows)
        ]


async def load_user_history_in_channel(bot_id: int, channel_id: int, user_id: int, limit: int = 10) -> List[Dict]:
    if db_pool is None:
        return []
    async with db_pool.acquire() as conn:
        rows = await conn.fetch("""
            SELECT role, content, username, created_at, message_id, author_id
            FROM messages
            WHERE bot_id = $1 AND channel_id = $2 AND author_id = $3
            ORDER BY id DESC LIMIT $4
        """, bot_id, channel_id, user_id, limit)
        return [
            {"role": r["role"], "content": r["content"], "username": r["username"], "created_at": r["created_at"]}
            for r in reversed(rows)
        ]


async def get_channel_history(bot_id: int, channel_id: int, limit: int = 10) -> List[Dict]:
    if db_pool is None:
        return []
    async with db_pool.acquire() as conn:
        rows = await conn.fetch("""
            SELECT role, content FROM messages
            WHERE bot_id = $1 AND channel_id = $2
            ORDER BY id DESC LIMIT $3
        """, bot_id, channel_id, limit)
        return [{"role": r["role"], "content": r["content"]} for r in reversed(rows)]


# ─────────────────────────────────────────────
#  Cleanup
# ─────────────────────────────────────────────

async def clear_channel_history(bot_id: int, channel_id: int):
    if db_pool is None:
        return
    async with db_pool.acquire() as conn:
        await conn.execute("DELETE FROM messages WHERE bot_id = $1 AND channel_id = $2", bot_id, channel_id)


async def delete_channel_records(bot_id: int, channel_id: int):
    if db_pool is None:
        return
    async with db_pool.acquire() as conn:
        await conn.execute("DELETE FROM messages WHERE bot_id = $1 AND channel_id = $2", bot_id, channel_id)
        await conn.execute("DELETE FROM dynamic_settings WHERE channel_id = $1", channel_id)


# ─────────────────────────────────────────────
#  Benchmarks  (stubs kept for compatibility)
# ─────────────────────────────────────────────

async def save_benchmark(bot_id: int, channel_id: int, author_id: int, response_time_seconds: float, response_chars: int, model: str):
    if db_pool is None:
        return
    async with db_pool.acquire() as conn:
        await conn.execute("""
            INSERT INTO benchmarks (bot_id, channel_id, author_id, response_time_seconds, response_chars, model)
            VALUES ($1, $2, $3, $4, $5, $6)
        """, bot_id, channel_id, author_id, response_time_seconds, response_chars, model)


async def save_search_query(*args, **kwargs):
    pass


async def save_search_documents(*args, **kwargs):
    pass