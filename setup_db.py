import asyncio
import aiomysql
import os
import logging
from dotenv import load_dotenv

load_dotenv()

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s")
logger = logging.getLogger("setup_db")

async def sync_database():
    logger.info("Initiating database synchronization...")
    try:
        connection = await aiomysql.connect(
            host=os.getenv("DB_HOST", "127.0.0.1"),
            port=int(os.getenv("DB_PORT", 3306)),
            user=os.getenv("DB_USER", "root"),
            password=os.getenv("DB_PASSWORD", ""),
            db=os.getenv("DB_NAME", "discord_ai"),
            autocommit=True
        )
        
        async with connection.cursor() as cursor:
            # Read the schema.sql file
            with open("schema.sql", "r", encoding="utf-8") as file:
                sql_script = file.read()
            
            # Split the script into individual commands based on semicolons
            commands = sql_script.split(';')
            
            # Execute each command
            for command in commands:
                if command.strip():
                    await cursor.execute(command)
            
            logger.info("Database migration completed successfully. Schema is synchronized.")
        
        connection.close()
    except Exception as e:
        logger.error(f"Failed to synchronize database: {e}")

if __name__ == "__main__":
    asyncio.run(sync_database())