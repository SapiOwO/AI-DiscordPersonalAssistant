import os
import time
import logging
import asyncio
from typing import List, Dict, Tuple, Any

import ollama
from dotenv import load_dotenv
import config

load_dotenv()
logger = logging.getLogger("ai_client")

OLLAMA_HOST = os.getenv("OLLAMA_HOST", None)

try:
    OLLAMA_TEMPERATURE = float(os.getenv("OLLAMA_TEMPERATURE", str(config.OLLAMA_TEMPERATURE)))
    OLLAMA_TOP_K = int(os.getenv("OLLAMA_TOP_K", str(config.OLLAMA_TOP_K)))
    OLLAMA_TOP_P = float(os.getenv("OLLAMA_TOP_P", str(config.OLLAMA_TOP_P)))
    OLLAMA_NUM_CTX = int(os.getenv("OLLAMA_NUM_CTX", str(config.OLLAMA_NUM_CTX)))
except (ValueError, TypeError):
    OLLAMA_TEMPERATURE = config.OLLAMA_TEMPERATURE
    OLLAMA_TOP_K = config.OLLAMA_TOP_K
    OLLAMA_TOP_P = config.OLLAMA_TOP_P
    OLLAMA_NUM_CTX = config.OLLAMA_NUM_CTX

def get_context_limits() -> Dict[str, Any]:
    num_ctx = max(1024, int(OLLAMA_NUM_CTX))

    if num_ctx <= 4096:
        return {
            "history_limit_owner": 24,
            "history_limit_user": 12,
            "rag_results": 2,
            "max_ram_messages": 8,
            "max_history_messages_in_prompt": 14,
            "max_history_chars_per_message": 420,
            "max_memory_chars": 900,
            "max_search_results_in_prompt": 3,
            "max_search_snippet_chars": 220,
        }

    if num_ctx <= 8192:
        return {
            "history_limit_owner": 60,
            "history_limit_user": 20,
            "rag_results": 3,
            "max_ram_messages": 12,
            "max_history_messages_in_prompt": 22,
            "max_history_chars_per_message": 560,
            "max_memory_chars": 1400,
            "max_search_results_in_prompt": 4,
            "max_search_snippet_chars": 280,
        }

    return {
        "history_limit_owner": 100,
        "history_limit_user": 30,
        "rag_results": 3,
        "max_ram_messages": 16,
        "max_history_messages_in_prompt": 32,
        "max_history_chars_per_message": 700,
        "max_memory_chars": 2200,
        "max_search_results_in_prompt": 5,
        "max_search_snippet_chars": 360,
    }

def make_ollama_client():
    kwargs = {}
    if OLLAMA_HOST:
        kwargs["host"] = OLLAMA_HOST
    return ollama.AsyncClient(**kwargs)

async def inspect_and_get_model_capabilities() -> Dict[str, bool]:
    return get_model_capabilities()

def get_model_capabilities() -> Dict[str, bool]:
    return {
        "supports_vision": config.MODEL_SUPPORTS_VISION,
        "supports_thinking": config.MODEL_SUPPORTS_THINKING,
        "supports_websearch": config.MODEL_SUPPORTS_WEBSEARCH
    }

async def chat_with_model(client: ollama.AsyncClient, model: str, messages: List[Dict], timeout_seconds: int = 120) -> Tuple[str, Dict]:
    start = time.time()
    options = {
        "temperature": OLLAMA_TEMPERATURE,
        "top_k": OLLAMA_TOP_K,
        "top_p": OLLAMA_TOP_P,
        "num_ctx": OLLAMA_NUM_CTX
    }

    try:
        task = asyncio.create_task(client.chat(model=model, messages=messages, options=options))
        resp = await asyncio.wait_for(task, timeout=timeout_seconds)
        elapsed = time.time() - start
        text = resp.get("message", {}).get("content", "")
        meta = {"tokens_est": int(len(text) / 4), "elapsed": elapsed}
        return text, meta
    except Exception:
        logger.exception("Model call error")
        raise