import re

MEMORY_CUES = [
    # Indonesian
    "ingat", "dulu", "kemarin", "tadi", "sebelumnya", "pernah", "bahas",
    "yang kita obrolin", "yang tadi", "kemarin itu", "repo", "project",
    "proyek", "bug", "file", "kode",

    # English
    "remember", "yesterday", "earlier", "before", "previously", "last time",
    "discussed", "we talked", "project", "code", "bug", "repo", "case study",
    "the previous", "that file", "that bug",

    # Japanese basic
    "覚えて", "昨日", "前に", "以前", "この前"
]

CASUAL_UTTERANCES = {
    "ok", "oke", "yes", "no", "lol", "wkwk", "haha", "thanks", "makasih",
    "nice", "iya", "siap", "siap bos", "yo", "hi", "halo", "hello"
}

AMBIGUOUS_REFERENCES = [
    "itu", "tadi", "yang itu", "yang tadi", "lanjut itu",
    "that", "that one", "the one", "previous one"
]

def determine_rag_mode(user_message: str) -> str:
    cleaned = user_message.strip().lower()

    if not cleaned:
        return "none"

    # 1. Explicit memory/project cues should win, even if the message is short.
    if any(cue in cleaned for cue in MEMORY_CUES):
        return "full"

    # 2. Ambiguous follow-up references need at least light memory.
    if any(ref in cleaned for ref in AMBIGUOUS_REFERENCES):
        return "light"

    # 3. Only skip clearly casual utterances (normalized from punctuation like !, ., ~)
    casual_key = re.sub(r"[^\w\s]", "", cleaned, flags=re.UNICODE).strip()
    if casual_key in CASUAL_UTTERANCES:
        return "none"

    # 4. Very short non-casual messages can still be ambiguous.
    if len(cleaned) <= 3:
        return "none"

    # 5. Safe fallback for meaningful input.
    return "light"

def build_memory_status_notice(rag_mode: str, has_memories: bool, prompt_mode: str = "full") -> str:
    if has_memories:
        return ""

    if prompt_mode == "lean":
        if rag_mode == "none":
            return "No long-term memory was retrieved. Do not claim prior memory unless shown in context.\n"
        else:
            return "Memory search was empty. Do not claim prior memory unless shown in context.\n"

    # Standard/Full mode notices
    if rag_mode == "none":
        return (
            "[SYSTEM NOTICE - MEMORY ABSENT]\n"
            "No long-term memory was retrieved for this turn. Do not claim to remember prior "
            "details unless they are present in the active context. If the user asks about "
            "missing past details, ask for clarification instead of guessing.\n"
        )
    else:  # searched but empty
        return (
            "[SYSTEM NOTICE - MEMORY SEARCH EMPTY]\n"
            "A long-term memory search was attempted, but no relevant memory was found. "
            "Do not invent prior details. If the user asks about missing past context, "
            "ask for clarification instead of guessing.\n"
        )
