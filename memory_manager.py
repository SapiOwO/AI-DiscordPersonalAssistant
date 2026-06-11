"""
Unified Memory Manager — pgvector on the messages table.

Embeddings are generated via local sentence-transformers (nomic-embed-text on CPU).
This runs on CPU and does NOT compete with GPU-based LLM inference.
Embeddings are written directly onto the same row in the `messages` table.
"""

import logging
from typing import List, Optional
import asyncio
from concurrent.futures import ThreadPoolExecutor

import httpx
import db
import config

logger = logging.getLogger("memory_manager")

EMBEDDING_MODEL = "nomic-ai/nomic-embed-text-v1.5"
EMBEDDING_DIM = 768

# Thread pool for CPU-based embedding inference (doesn't block async)
_embedding_executor = ThreadPoolExecutor(max_workers=2)
_embedding_model = None


def _get_embedding_model():
    """Lazy-load the embedding model on first use."""
    global _embedding_model
    if _embedding_model is None:
        engine = getattr(config, "EMBEDDING_ENGINE", "ollama").lower()
        if engine == "ollama":
            logger.info("Using Ollama-based embeddings (nomic-embed-text).")
            _embedding_model = False  # Flag to use Ollama
            return _embedding_model

        try:
            from sentence_transformers import SentenceTransformer
            logger.info(f"Loading {EMBEDDING_MODEL} (CPU-based, no GPU competition)...")
            _embedding_model = SentenceTransformer(EMBEDDING_MODEL, device="cpu", trust_remote_code=True)
            logger.info(f"Embedding model loaded. Dimension: {EMBEDDING_DIM}")
        except Exception as e:
            logger.error(f"Failed to load sentence-transformers: {e}. Falling back to Ollama.")
            _embedding_model = False  # Flag to use Ollama fallback
    return _embedding_model


async def _get_embedding_ollama_fallback(text: str) -> List[float]:
    """Fallback to Ollama if sentence-transformers is not available."""
    if not text or not text.strip():
        return []
    try:
        async with httpx.AsyncClient() as client:
            resp = await client.post(
                "http://localhost:11434/api/embeddings",
                json={
                    "model": "nomic-embed-text",
                    "prompt": text[:2000],
                    "keep_alive": "30m"
                },
                timeout=15.0,
            )
            if resp.status_code == 200:
                vec = resp.json().get("embedding", [])
                if len(vec) == EMBEDDING_DIM:
                    return vec
                logger.warning(f"Embedding dimension mismatch: got {len(vec)}, expected {EMBEDDING_DIM}")
                return []
            logger.warning(f"Ollama embedding HTTP {resp.status_code}: {resp.text[:200]}")
            return []
    except Exception as e:
        logger.error(f"Ollama embedding fallback failed: {e}")
        return []


# ─────────────────────────────────────────────
#  Embedding generation
# ─────────────────────────────────────────────

async def get_embedding(text: str) -> List[float]:
    """Request a 768-dim embedding from local nomic-embed-text model (CPU, no GPU).
    
    Falls back to Ollama if sentence-transformers is not installed.
    """
    if not text or not text.strip():
        return []
    
    model = _get_embedding_model()
    
    # Use Ollama fallback if model failed to load
    if model is False:
        return await _get_embedding_ollama_fallback(text)
    
    try:
        # Run CPU embedding in thread pool to avoid blocking async loop
        loop = asyncio.get_event_loop()
        embedding = await loop.run_in_executor(
            _embedding_executor,
            lambda: model.encode(text[:2000], convert_to_numpy=True).tolist()
        )
        
        if len(embedding) == EMBEDDING_DIM:
            return embedding
        else:
            logger.warning(f"Embedding dimension mismatch: got {len(embedding)}, expected {EMBEDDING_DIM}")
            return []
    except Exception as e:
        logger.error(f"Local embedding failed: {e}. Trying Ollama fallback...")
        return await _get_embedding_ollama_fallback(text)


# ─────────────────────────────────────────────
#  Write embeddings  (unified on messages table)
# ─────────────────────────────────────────────

async def embed_message(row_id: Optional[int], text_override: Optional[str] = None):
    """
    Generate an embedding and store it on an existing messages row.

    Parameters
    ----------
    row_id : int
        The ``messages.id`` returned by ``db.save_message()``.
    text_override : str, optional
        If provided, embed this text instead of the stored content.
        Useful for enriched image descriptions.
    """
    if row_id is None:
        return

    # Determine text to embed
    embed_text = text_override
    if not embed_text:
        # Read the content from the DB row
        if db.db_pool is None:
            return
        async with db.db_pool.acquire() as conn:
            row = await conn.fetchrow("SELECT content FROM messages WHERE id = $1", row_id)
            if not row:
                return
            embed_text = row["content"]

    if not embed_text or not embed_text.strip():
        return

    embedding = await get_embedding(embed_text)
    if not embedding:
        return

    await db.update_message_embedding(row_id, embedding)
    logger.debug(f"Embedded message row {row_id} ({len(embed_text)} chars)")


# ─────────────────────────────────────────────
#  RAG search  (unified on messages table)
# ─────────────────────────────────────────────

async def search_memory(context_id: int, guild_id: Optional[int], query: str, n_results: int = 3) -> str:
    """
    Semantic search over past messages in the current conversational scope.

    Returns a formatted string ready for injection into the prompt,
    or an empty string if nothing relevant was found.
    """
    if not query or not query.strip():
        return ""

    embedding = await get_embedding(query)
    if not embedding:
        return ""

    try:
        rows = await db.vector_search_messages(context_id, guild_id, embedding, n_results)
        if not rows:
            return ""

        lines = []
        for r in rows:
            ts = r["created_at"]
            t = ts.strftime("%Y-%m-%d %H:%M") if ts else "?"
            role = (r.get("role") or "user").upper()
            content = r.get("content") or ""
            lines.append(f"[{t}] {role}: {content}")
        return "\n".join(lines)

    except Exception as e:
        logger.error(f"Vector search failed: {e}")
        return ""