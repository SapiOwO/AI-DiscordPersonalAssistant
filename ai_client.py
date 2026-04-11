import os
import time
import logging
import asyncio
from typing import List, Dict, Tuple

import ollama
from dotenv import load_dotenv
import config

load_dotenv()
logger = logging.getLogger("ai_client")

OLLAMA_HOST = os.getenv("OLLAMA_HOST", None)

try:
    OLLAMA_TEMPERATURE = float(os.getenv("OLLAMA_TEMPERATURE", "0.7"))
    OLLAMA_TOP_K = int(os.getenv("OLLAMA_TOP_K", "40"))
    OLLAMA_TOP_P = float(os.getenv("OLLAMA_TOP_P", "0.9"))
    OLLAMA_NUM_CTX = int(os.getenv("OLLAMA_NUM_CTX", "2048"))
except (ValueError, TypeError):
    OLLAMA_TEMPERATURE = 0.7
    OLLAMA_TOP_K = 40
    OLLAMA_TOP_P = 0.9
    OLLAMA_NUM_CTX = 2048

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