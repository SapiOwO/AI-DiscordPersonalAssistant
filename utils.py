import re
from typing import Generator, Optional, Tuple

NAME_PATTERNS = [
    re.compile(r"\b(?:my name is|call me|i'm|i am)\s+([A-Za-z0-9 _\-]{2,50})", flags=re.I),
]

THINKING_START = r"<<<THINKING>>>"
THINKING_END = r"<<<ENDTHINKING>>>"


def chunk_text(text: str, size: int = 1900) -> Generator[str, None, None]:
    if not text:
        return
    if size <= 0:
        raise ValueError("size must be greater than zero")

    text = str(text)
    start = 0
    length = len(text)

    while start < length:
        end = min(start + size, length)

        if end < length:
            split_at = max(
                text.rfind("\n", start, end),
                text.rfind(" ", start, end),
            )
            if split_at > start + max(1, size // 2):
                end = split_at

        chunk = text[start:end].strip()
        if chunk:
            yield chunk

        start = end
        while start < length and text[start] in " \r\n\t":
            start += 1


def extract_given_name(text: str) -> Optional[str]:
    if not text:
        return None

    for pattern in NAME_PATTERNS:
        match = pattern.search(text)
        if match:
            candidate = match.group(1).strip()
            candidate = re.sub(r"[^\w\s\-]", "", candidate).strip()
            if len(candidate) >= 2:
                return candidate
    return None


def parse_thinking_and_response(text: str) -> Tuple[Optional[str], str]:
    if not text:
        return None, ""

    pattern = re.compile(rf"{THINKING_START}\s*(.*?)\s*{THINKING_END}", re.DOTALL | re.IGNORECASE)
    match = pattern.search(text)

    if match:
        thinking = match.group(1).strip()
        main = pattern.sub("", text).strip()
        thinking = re.sub(r"\n\s*\n+", "\n\n", thinking)
        main = re.sub(r"\n\s*\n+", "\n\n", main)
        return thinking, main

    return None, text.strip()