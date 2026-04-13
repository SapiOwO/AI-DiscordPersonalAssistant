import asyncio
import logging
from datetime import datetime
import chromadb

logger = logging.getLogger("memory_manager")

chroma_client = chromadb.PersistentClient(path="./chroma_db")
collection = chroma_client.get_or_create_collection(name="episodic_memory")

def _save_memory_sync(user_id: int, username: str, role: str, content: str, message_id: str):
    if not content or len(content) < 3:
        return
        
    doc_id = f"{user_id}_{message_id}"
    metadata = {
        "user_id": str(user_id),
        "username": username,
        "role": role,
        "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    }
    
    try:
        collection.add(
            documents=[content],
            metadatas=[metadata],
            ids=[doc_id]
        )
    except Exception as e:
        logger.error(f"Failed to save vector memory: {e}")

async def save_memory(user_id: int, username: str, role: str, content: str, message_id: str):
    await asyncio.to_thread(_save_memory_sync, user_id, username, role, content, message_id)

def _search_memory_sync(user_id: int, query: str, n_results: int = 3) -> str:
    if not query or len(query) < 3:
        return ""
        
    try:
        results = collection.query(
            query_texts=[query],
            n_results=n_results,
            where={"user_id": str(user_id)}
        )
        
        if not results['documents'] or not results['documents'][0]:
            return ""
            
        memories = []
        for doc, meta in zip(results['documents'][0], results['metadatas'][0]):
            time_str = meta.get("timestamp", "")
            role = meta.get("role", "unknown").upper()
            memories.append(f"[{time_str}] {role}: {doc}")
            
        return "\n".join(memories)
    except Exception as e:
        logger.error(f"Failed to search vector memory: {e}")
        return ""

async def search_memory(user_id: int, query: str, n_results: int = 3) -> str:
    return await asyncio.to_thread(_search_memory_sync, user_id, query, n_results)