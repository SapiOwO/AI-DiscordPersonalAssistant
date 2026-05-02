"""
Unified Memory Manager — pgvector on the messages table.

Embeddings are generated via Ollama's nomic-embed-text and written
directly onto the same row in the `messages` table that holds the
chat content.  No separate vector table is needed.
"""

import logging
from typing import List, Optional

import httpx
import db

logger = logging.getLogger("memory_manager")

OLLAMA_EMBED_URL = "http://localhost:11434/api/embeddings"
EMBEDDING_MODEL = "nomic-embed-text"
EMBEDDING_DIM = 768


# ─────────────────────────────────────────────
#  Embedding generation
# ─────────────────────────────────────────────

async def get_embedding(text: str) -> List[float]:
    """Request a 768-dim embedding from Ollama nomic-embed-text."""
    if not text or not text.strip():
        return []
    try:
        async with httpx.AsyncClient() as client:
            resp = await client.post(
                OLLAMA_EMBED_URL,
                json={"model": EMBEDDING_MODEL, "prompt": text[:2000]},
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
        logger.error(f"Embedding request failed: {e}")
        return []


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