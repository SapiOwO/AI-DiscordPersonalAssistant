import logging
from typing import List, Dict, Optional
from urllib.parse import urlparse

import aiohttp

logger = logging.getLogger("websearch")

GOOGLE_CUSTOM_SEARCH_URL = "https://www.googleapis.com/customsearch/v1"


def _normalize_host(value: str) -> str:
    host = (value or "").strip().lower()
    if "://" in host:
        host = urlparse(host).hostname or ""
    host = host.lower()
    if host.startswith("www."):
        host = host[4:]
    return host


def _domain_allowed(link: str, allowed_domains: Optional[List[str]]) -> bool:
    if not allowed_domains:
        return True

    host = _normalize_host(urlparse(link).netloc)
    if not host:
        return False

    normalized_allowed = [_normalize_host(domain) for domain in allowed_domains if domain]
    for allowed in normalized_allowed:
        if not allowed:
            continue
        if host == allowed or host.endswith("." + allowed):
            return True
    return False


async def google_search(
    query: str,
    api_key: str,
    cse_id: str,
    allowed_domains: Optional[List[str]] = None,
    num: int = 5,
    session: Optional[aiohttp.ClientSession] = None,
) -> List[Dict]:
    if not api_key or not cse_id or not query:
        return []

    num = max(1, min(int(num), 10))
    params = {
        "key": api_key,
        "cx": cse_id,
        "q": query,
        "num": num,
        "safe": "active",
        "fields": "items(title,link,snippet,displayLink)",
    }

    close_session = False
    if session is None:
        timeout = aiohttp.ClientTimeout(total=20)
        session = aiohttp.ClientSession(timeout=timeout)
        close_session = True

    try:
        async with session.get(GOOGLE_CUSTOM_SEARCH_URL, params=params) as resp:
            resp.raise_for_status()
            data = await resp.json()
    except Exception:
        logger.exception("Google search failed")
        if close_session:
            await session.close()
        return []
    finally:
        if close_session and not session.closed:
            await session.close()

    results: List[Dict] = []
    items = data.get("items", []) or []

    for item in items:
        title = item.get("title")
        link = item.get("link")
        snippet = item.get("snippet") or ""
        display_link = item.get("displayLink") or ""

        if not link:
            continue
        if not _domain_allowed(link, allowed_domains):
            continue

        results.append(
            {
                "title": title,
                "link": link,
                "snippet": snippet,
                "display_link": display_link,
            }
        )

    return results