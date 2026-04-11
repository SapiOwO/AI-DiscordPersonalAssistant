# websearch.py
import aiohttp
import logging
from typing import List, Dict, Optional
from urllib.parse import urlparse

logger = logging.getLogger("websearch")

GOOGLE_CUSTOM_SEARCH_URL = "https://www.googleapis.com/customsearch/v1"

async def google_search(query: str, api_key: str, cse_id: str, allowed_domains: Optional[List[str]] = None, num: int = 5) -> List[Dict]:
    params = {"key": api_key, "cx": cse_id, "q": query, "num": num}
    results = []
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(GOOGLE_CUSTOM_SEARCH_URL, params=params, timeout=20) as resp:
                data = await resp.json()
    except Exception:
        logger.exception("Google search failed")
        return []
    
    items = data.get("items", []) or []
    for it in items:
        title = it.get("title")
        link = it.get("link")
        snippet = it.get("snippet") or ""
        if allowed_domains:
            try:
                domain = urlparse(link).netloc.lower()
            except Exception:
                domain = ""
            
            allow = any(ad.lower() in domain for ad in allowed_domains)
            if not allow:
                continue
        results.append({"title": title, "link": link, "snippet": snippet})
    return results