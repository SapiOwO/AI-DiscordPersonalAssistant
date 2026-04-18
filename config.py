import os
import logging
from typing import List, Optional

from dotenv import load_dotenv

load_dotenv()
logger = logging.getLogger("config")

def get_env_var(key: str, default: Optional[str] = None) -> Optional[str]:
    return os.getenv(key, default)

def get_bool_env_var(key: str, default: bool = False) -> bool:
    value = get_env_var(key, str(default))
    return value.lower() in ("true", "1", "yes", "y")

def get_int_env_var(key: str, default: int) -> int:
    try:
        return int(get_env_var(key, str(default)))
    except (ValueError, TypeError):
        return default

def get_float_env_var(key: str, default: float) -> float:
    try:
        return float(get_env_var(key, str(default)))
    except (ValueError, TypeError):
        return default

def get_list_env_var(key: str) -> List[str]:
    value = get_env_var(key, "")
    return [item.strip() for item in value.split(',') if item.strip()]

# --- DISCORD CORE ---
DISCORD_TOKEN: Optional[str] = get_env_var("DISCORD_TOKEN")
OWNER_IDS: List[int] = [int(uid) for uid in get_list_env_var("OWNER_IDS")]
ALLOW_DMS: bool = get_bool_env_var("ALLOW_DMS", False)
TARGET_CHANNEL_IDS: List[int] = [int(cid) for cid in get_list_env_var("TARGET_CHANNEL_IDS")]
SHOW_FOOTER_INFO_DEFAULT: bool = get_bool_env_var("SHOW_FOOTER_INFO_DEFAULT", True)

# --- OLLAMA MAIN BRAIN ---
OLLAMA_HOST: Optional[str] = get_env_var("OLLAMA_HOST", "http://localhost:11434")
OLLAMA_MODEL: str = get_env_var("OLLAMA_MODEL", "gemma4:e4b-it-q4_K_M")
OLLAMA_TIMEOUT: float = get_float_env_var("OLLAMA_TIMEOUT", 120.0)

# --- MODEL CAPABILITIES ---
MODEL_SUPPORTS_VISION: bool = get_bool_env_var("MODEL_SUPPORTS_VISION", True)
MODEL_SUPPORTS_THINKING: bool = get_bool_env_var("MODEL_SUPPORTS_THINKING", False)
MODEL_SUPPORTS_WEBSEARCH: bool = get_bool_env_var("MODEL_SUPPORTS_WEBSEARCH", True)
OMNIPRESENT_MEMORY: bool = get_bool_env_var("OMNIPRESENT_MEMORY", False)

# --- INFERENCE PARAMETERS ---
OLLAMA_TEMPERATURE: float = get_float_env_var("OLLAMA_TEMPERATURE", 0.7)
OLLAMA_TOP_K: int = get_int_env_var("OLLAMA_TOP_K", 40)
OLLAMA_TOP_P: float = get_float_env_var("OLLAMA_TOP_P", 0.9)
OLLAMA_NUM_CTX: int = get_int_env_var("OLLAMA_NUM_CTX", 8192)

# --- STATUS & ACTIVITY ---
STATUS_MESSAGE: str = get_env_var("STATUS_MESSAGE", "your heart")
STATUS_TYPE: str = get_env_var("STATUS_TYPE", "listening").lower()

# --- EXTERNAL SERVICES ---
IMAGINE_COOLDOWN_SECONDS: int = get_int_env_var("IMAGINE_COOLDOWN_SECONDS", 60)
STABLE_DIFFUSION_URL: Optional[str] = get_env_var("STABLE_DIFFUSION_URL")
FONT_PATH: Optional[str] = get_env_var("FONT_PATH")
GOOGLE_API_KEY: Optional[str] = get_env_var("GOOGLE_API_KEY")
GOOGLE_CSE_ID: Optional[str] = get_env_var("GOOGLE_CSE_ID")
GOOGLE_ALLOWED_DOMAINS: List[str] = get_list_env_var("GOOGLE_ALLOWED_DOMAINS")

# --- AUDIO & UTILS ---
FFMPEG_PATH: str = get_env_var("FFMPEG_PATH", "ffmpeg")
INACTIVITY_TIMEOUT: int = get_int_env_var("INACTIVITY_TIMEOUT", 60)
IMAGE_MAX_DIMENSION: int = get_int_env_var("IMAGE_MAX_DIMENSION", 1024)
IMAGE_COMPRESSION_QUALITY: int = get_int_env_var("IMAGE_COMPRESSION_QUALITY", 85)

# --- RESPONSE TEMPLATES ---
RESPONSE_TEMPLATES = {
    "audio_failed": get_env_var("MSG_AUDIO_FAILED", "*(voice note couldn't be generated, sorry!)*"),
    "memory_wiped_channel": get_env_var("MSG_MEMORY_WIPED_CHANNEL", "Memory wiped for this channel."),
    "memory_wiped_personal": get_env_var("MSG_MEMORY_WIPED_PERSONAL", "Personal memory wiped."),
    "error_generic": get_env_var("MSG_ERROR_GENERIC", "⚠️ Something went wrong while processing your request."),
    "error_timeout": get_env_var("MSG_ERROR_TIMEOUT", "⚠️ The AI took too long to respond. Please try again."),
    "error_download": get_env_var("MSG_ERROR_DOWNLOAD", "⚠️ Failed to download the attached file. Try again."),
}