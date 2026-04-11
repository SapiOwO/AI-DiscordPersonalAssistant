import os
import logging
from datetime import datetime
from typing import Optional, List, Dict, Any

import aiomysql
from dotenv import load_dotenv

load_dotenv()
logger = logging.getLogger("db")

DB_HOST = os.getenv("DB_HOST", "127.0.0.1")
DB_PORT = int(os.getenv("DB_PORT", "3306"))
DB_USER = os.getenv("DB_USER", "bot_user")
DB_PASSWORD = os.getenv("DB_PASSWORD", "change_me")
DB_NAME = os.getenv("DB_NAME", "discord_ai")

db_pool: Optional[aiomysql.Pool] = None

DEFAULT_GUILD_SETTINGS = {
    "persona_enabled": "False",
    "persona_text": os.getenv("DEFAULT_PERSONA", "You are a helpful AI assistant."),
    "show_footer_info": os.getenv("SHOW_FOOTER_INFO_DEFAULT", "True")
}

async def init_db():
    global db_pool
    db_pool = await aiomysql.create_pool(
        host=DB_HOST, port=DB_PORT, user=DB_USER, password=DB_PASSWORD,
        db=DB_NAME, autocommit=True, minsize=1, maxsize=10, charset="utf8mb4"
    )
    logger.info("DB initialized.")

async def get_guild_setting(guild_id: int, bot_id: int, key: str) -> Optional[str]:
    if db_pool is None: return DEFAULT_GUILD_SETTINGS.get(key)
    async with db_pool.acquire() as conn:
        async with conn.cursor() as cur:
            await cur.execute("SELECT setting_value FROM guild_settings WHERE guild_id = %s AND bot_id = %s AND setting_key = %s", (guild_id, bot_id, key))
            result = await cur.fetchone()
            if result:
                return result[0]
            return DEFAULT_GUILD_SETTINGS.get(key)

async def set_guild_setting(guild_id: int, bot_id: int, key: str, value: Any):
    if db_pool is None: return
    async with db_pool.acquire() as conn:
        async with conn.cursor() as cur:
            await cur.execute(
                """INSERT INTO guild_settings (guild_id, bot_id, setting_key, setting_value)
                   VALUES (%s, %s, %s, %s) AS new
                   ON DUPLICATE KEY UPDATE setting_value = new.setting_value""",
                (guild_id, bot_id, key, str(value))
            )

async def get_or_create_profile(user_id: int, bot_id: int, username: str) -> Dict:
    now = datetime.utcnow()
    async with db_pool.acquire() as conn:
        async with conn.cursor(aiomysql.DictCursor) as cur:
            await cur.execute("SELECT * FROM profiles WHERE user_id=%s AND bot_id=%s", (user_id, bot_id))
            r = await cur.fetchone()
            if r:
                return r
            else:
                await cur.execute(
                    "INSERT INTO profiles (user_id, bot_id, username, updated_at) VALUES (%s, %s, %s, %s)",
                    (user_id, bot_id, username, now)
                )
                return {"user_id": user_id, "bot_id": bot_id, "username": username, "given_name": None, "last_imagine_timestamp": None}

async def update_profile_imagine_timestamp(user_id: int, bot_id: int):
    if db_pool is None: return
    now = datetime.utcnow()
    async with db_pool.acquire() as conn:
        async with conn.cursor() as cur:
            await cur.execute("UPDATE profiles SET last_imagine_timestamp=%s WHERE user_id=%s AND bot_id=%s", (now, user_id, bot_id))

async def save_message(bot_id: int, channel_id: int, message_id: Optional[int], author_id: Optional[int], username: Optional[str], role: str, content: str):
    if db_pool is None: return
    now = datetime.utcnow()
    async with db_pool.acquire() as conn:
        async with conn.cursor() as cur:
            await cur.execute(
                "INSERT INTO messages (bot_id, channel_id, message_id, author_id, username, role, content, created_at) VALUES (%s, %s, %s, %s, %s, %s, %s, %s)",
                (bot_id, channel_id, message_id, author_id, username, role, content, now)
            )

async def load_conversation_context(bot_id: int, context_id: int, limit: int = 50, owner_id: Optional[int] = None, omnipresent: bool = False) -> List[Dict]:
    if db_pool is None: return []
    async with db_pool.acquire() as conn:
        async with conn.cursor(aiomysql.DictCursor) as cur:
            if omnipresent and owner_id:
                await cur.execute("""
                    SELECT role, content, author_id, username, created_at 
                    FROM messages 
                    WHERE bot_id=%s AND (channel_id=%s OR channel_id=%s) 
                    ORDER BY id DESC LIMIT %s
                """, (bot_id, context_id, owner_id, limit))
            else:
                await cur.execute("""
                    SELECT role, content, author_id, username, created_at 
                    FROM messages 
                    WHERE bot_id=%s AND channel_id=%s 
                    ORDER BY id DESC LIMIT %s
                """, (bot_id, context_id, limit))
            rows = await cur.fetchall()
            return list(reversed(rows))

async def load_user_history_in_channel(bot_id: int, context_id: int, user_id: int, limit: int = 10) -> List[Dict]:
    if db_pool is None: return []
    async with db_pool.acquire() as conn:
        async with conn.cursor(aiomysql.DictCursor) as cur:
            await cur.execute("SELECT role, content, author_id, username, message_id, created_at FROM messages WHERE bot_id=%s AND channel_id=%s AND author_id=%s ORDER BY id DESC LIMIT %s", (bot_id, context_id, user_id, limit))
            rows = await cur.fetchall()
            return list(reversed(rows))

async def clear_channel_history(bot_id: int, channel_id: int):
    if db_pool is None: return
    async with db_pool.acquire() as conn:
        async with conn.cursor() as cur:
            await cur.execute("DELETE FROM messages WHERE bot_id=%s AND channel_id=%s", (bot_id, channel_id))

async def delete_channel_records(bot_id: int, channel_id: int):
    if db_pool is None: return
    async with db_pool.acquire() as conn:
        async with conn.cursor() as cur:
            await cur.execute("DELETE FROM messages WHERE bot_id=%s AND channel_id=%s", (bot_id, channel_id))