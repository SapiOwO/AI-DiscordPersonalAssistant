import asyncio
import logging
import os
from pathlib import Path

import aiomysql
from dotenv import load_dotenv

load_dotenv()

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s")
logger = logging.getLogger("setup_db")

DB_HOST = os.getenv("DB_HOST", "127.0.0.1")
DB_PORT = int(os.getenv("DB_PORT", 3306))
DB_USER = os.getenv("DB_USER", "root")
DB_PASSWORD = os.getenv("DB_PASSWORD", "")
DB_NAME = os.getenv("DB_NAME", "discord_ai")

SCHEMA_PATH = Path(__file__).with_name("schema.sql")


def split_sql_script(script: str) -> list[str]:
    statements: list[str] = []
    buffer: list[str] = []

    in_single = False
    in_double = False
    in_backtick = False
    in_line_comment = False
    in_block_comment = False

    i = 0
    length = len(script)

    while i < length:
        ch = script[i]
        nxt = script[i + 1] if i + 1 < length else ""
        prev = script[i - 1] if i > 0 else ""

        if in_line_comment:
            if ch == "\n":
                in_line_comment = False
                buffer.append(ch)
            i += 1
            continue

        if in_block_comment:
            if ch == "*" and nxt == "/":
                in_block_comment = False
                i += 2
                continue
            i += 1
            continue

        if not (in_single or in_double or in_backtick):
            if ch == "#" :
                in_line_comment = True
                i += 1
                continue
            if ch == "-" and nxt == "-" and (i + 2 >= length or script[i + 2].isspace()):
                in_line_comment = True
                i += 2
                continue
            if ch == "/" and nxt == "*":
                in_block_comment = True
                i += 2
                continue

        if ch == "'" and not in_double and not in_backtick:
            if prev != "\\":
                in_single = not in_single
            buffer.append(ch)
            i += 1
            continue

        if ch == '"' and not in_single and not in_backtick:
            if prev != "\\":
                in_double = not in_double
            buffer.append(ch)
            i += 1
            continue

        if ch == "`" and not in_single and not in_double:
            in_backtick = not in_backtick
            buffer.append(ch)
            i += 1
            continue

        if ch == ";" and not (in_single or in_double or in_backtick):
            statement = "".join(buffer).strip()
            if statement:
                statements.append(statement)
            buffer = []
            i += 1
            continue

        buffer.append(ch)
        i += 1

    tail = "".join(buffer).strip()
    if tail:
        statements.append(tail)

    return statements


async def sync_database():
    logger.info("Initiating database synchronization...")
    admin_conn = None
    db_conn = None

    try:
        admin_conn = await aiomysql.connect(
            host=DB_HOST,
            port=DB_PORT,
            user=DB_USER,
            password=DB_PASSWORD,
            autocommit=True,
        )
        async with admin_conn.cursor() as cursor:
            await cursor.execute(
                f"CREATE DATABASE IF NOT EXISTS `{DB_NAME}` CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci"
            )

        db_conn = await aiomysql.connect(
            host=DB_HOST,
            port=DB_PORT,
            user=DB_USER,
            password=DB_PASSWORD,
            db=DB_NAME,
            autocommit=True,
        )

        schema_sql = SCHEMA_PATH.read_text(encoding="utf-8")
        statements = split_sql_script(schema_sql)

        async with db_conn.cursor() as cursor:
            for statement in statements:
                stmt = statement.strip()
                if not stmt:
                    continue
                await cursor.execute(stmt)

        logger.info("Database migration completed successfully. Schema is synchronized.")
    except Exception as e:
        logger.error(f"Failed to synchronize database: {e}", exc_info=True)
        raise
    finally:
        if db_conn is not None:
            db_conn.close()
            try:
                await db_conn.wait_closed()
            except Exception:
                pass
        if admin_conn is not None:
            admin_conn.close()
            try:
                await admin_conn.wait_closed()
            except Exception:
                pass


if __name__ == "__main__":
    asyncio.run(sync_database())