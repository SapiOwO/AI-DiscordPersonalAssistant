import asyncio
import logging
from datetime import datetime

import chromadb

logger = logging.getLogger("memory_manager")

PREFERRED_ONNX_PROVIDERS = ("CUDAExecutionProvider", "CPUExecutionProvider")
MAX_MEMORY_ITEM_CHARS = 500
MAX_MEMORY_TOTAL_CHARS = 2000

try:
    from chromadb.utils.embedding_functions.onnx_mini_lm_l6_v2 import ONNXMiniLM_L6_V2
except Exception:
    ONNXMiniLM_L6_V2 = None

def _truncate_text(value: str, max_chars: int) -> str:
    text = value if isinstance(value, str) else str(value)
    if len(text) <= max_chars:
        return text
    if max_chars <= 3:
        return text[:max_chars]
    return text[: max_chars - 3].rstrip() + "..."

def _resolve_preferred_providers():
    try:
        import onnxruntime as ort

        available = set(ort.get_available_providers())
        selected = [provider for provider in PREFERRED_ONNX_PROVIDERS if provider in available]
        if selected:
            return selected
        if "CPUExecutionProvider" in available:
            return ["CPUExecutionProvider"]
    except Exception as e:
        logger.debug(f"Could not resolve ONNX providers: {e}")
    return None

if ONNXMiniLM_L6_V2 is not None:
    class _DefaultCompatibleONNXEmbedding(ONNXMiniLM_L6_V2):
        def __init__(self):
            super().__init__(preferred_providers=_resolve_preferred_providers())

        @staticmethod
        def name() -> str:
            return "default"

        @staticmethod
        def build_from_config(config):
            return _DefaultCompatibleONNXEmbedding()

        def get_config(self):
            return {}

        def validate_config_update(self, old_config, new_config):
            return

        @staticmethod
        def validate_config(config):
            return
else:
    _DefaultCompatibleONNXEmbedding = None

try:
    chroma_client = chromadb.PersistentClient(path="./chroma_db")
    if _DefaultCompatibleONNXEmbedding is not None:
        try:
            collection = chroma_client.get_or_create_collection(
                name="episodic_memory",
                embedding_function=_DefaultCompatibleONNXEmbedding(),
            )
        except Exception as e:
            logger.warning(f"Falling back to default Chroma embedding init: {e}")
            collection = chroma_client.get_or_create_collection(name="episodic_memory")
    else:
        collection = chroma_client.get_or_create_collection(name="episodic_memory")
except Exception as e:
    logger.error(f"Failed to initialize ChromaDB: {e}")
    collection = None

def _save_memory_sync(user_id: int, username: str, role: str, content: str, message_id: str):
    if not collection or not content or len(content) < 3:
        return

    doc_id = f"{user_id}_{message_id}"
    metadata = {
        "user_id": str(user_id),
        "username": username,
        "role": role,
        "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
    }

    try:
        collection.add(documents=[content], metadatas=[metadata], ids=[doc_id])
    except Exception as e:
        logger.error(f"Failed to save vector memory: {e}")

async def save_memory(user_id: int, username: str, role: str, content: str, message_id: str):
    await asyncio.to_thread(_save_memory_sync, user_id, username, role, content, message_id)

def _search_memory_sync(user_id: int, query: str, n_results: int = 3) -> str:
    if not collection or not query or len(query) < 3:
        return ""

    try:
        results = collection.query(
            query_texts=[query],
            n_results=n_results,
            where={"user_id": str(user_id)},
        )

        if not results["documents"] or not len(results["documents"][0]):
            return ""

        memories = []
        total_chars = 0
        for doc, meta in zip(results["documents"][0], results["metadatas"][0]):
            time_str = meta.get("timestamp", "")
            role = meta.get("role", "unknown").upper()
            compact_doc = _truncate_text(doc, MAX_MEMORY_ITEM_CHARS)
            memory_row = f"[{time_str}] {role}: {compact_doc}"

            if total_chars + len(memory_row) > MAX_MEMORY_TOTAL_CHARS:
                break

            memories.append(memory_row)
            total_chars += len(memory_row)

        return "\n".join(memories)
    except Exception as e:
        logger.error(f"Failed to search vector memory: {e}")
        return ""

async def search_memory(user_id: int, query: str, n_results: int = 3) -> str:
    return await asyncio.to_thread(_search_memory_sync, user_id, query, n_results)