import asyncio
import logging
import os
from pathlib import Path
import asyncpg
from dotenv import load_dotenv

load_dotenv()

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s")
logger = logging.getLogger("setup_db")

DB_HOST = os.getenv("DB_HOST", "127.0.0.1")
DB_PORT = os.getenv("DB_PORT", "5432")
DB_USER = os.getenv("DB_USER", "postgres")
DB_PASSWORD = os.getenv("DB_PASS", "admin")
DB_NAME = os.getenv("DB_NAME", "discord_ai")

SCHEMA_PATH = Path(__file__).with_name("schema.sql")

async def main():
    try:
        logger.info(f"Connecting to PostgreSQL database: {DB_NAME}...")
        conn = await asyncpg.connect(
            host=DB_HOST,
            port=DB_PORT,
            user=DB_USER,
            password=DB_PASSWORD,
            database=DB_NAME
        )
        
        logger.info("Reading schema.sql...")
        schema_sql = SCHEMA_PATH.read_text(encoding="utf-8")
        
        logger.info("Executing schema script to create tables...")
        await conn.execute(schema_sql)
        
        logger.info("Database migration completed successfully. Tables are ready!")
        await conn.close()
        
    except Exception as e:
        logger.error(f"Failed to set up database: {e}")

if __name__ == "__main__":
    asyncio.run(main())