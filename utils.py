# utils.py
import re
from typing import Generator, Optional, Tuple

def estimate_tokens(text: str) -> int:
    if not text:
        return 0
    return max(1, int(len(text) / 4))

def chunk_text(text: str, size: int = 1900) -> Generator[str, None, None]:
    for i in range(0, len(text), size):
        yield text[i:i+size]

NAME_PATTERNS = [
    re.compile(r"\b(?:my name is|call me|i'm|i am)\s+([A-Za-z0-9 _\-]{2,50})", flags=re.I),
]

def extract_given_name(text: str) -> Optional[str]:
    if not text:
        return None
    for p in NAME_PATTERNS:
        m = p.search(text)
        if m:
            candidate = m.group(1).strip()
            candidate = re.sub(r"[^\w\s\-]", "", candidate).strip()
            if len(candidate) >= 2:
                return candidate
    return None

THINKING_START = r"<<<THINKING>>>"
THINKING_END = r"<<<ENDTHINKING>>>"

def parse_thinking_and_response(text: str) -> Tuple[Optional[str], str]:
    if not text:
        return None, ""
    pattern = re.compile(rf"{THINKING_START}\s*(.*?)\s*{THINKING_END}", re.DOTALL | re.IGNORECASE)
    m = pattern.search(text)
    if m:
        thinking = m.group(1).strip()
        main = pattern.sub("", text).strip()
        thinking = re.sub(r"\n\s*\n+", "\n\n", thinking)
        main = re.sub(r"\n\s*\n+", "\n\n", main)
        return thinking, main
    return None, text.strip()