from __future__ import annotations
import time
import httpx
from ..config import SEMANTIC_SCHOLAR_API_KEY, MAX_RETRIES, RETRY_BACKOFF_BASE


BASE = "https://api.semanticscholar.org/graph/v1"


def _headers() -> dict[str, str]:
    h = {"User-Agent": "citeagle/0.1.0"}
    if SEMANTIC_SCHOLAR_API_KEY:
        h["x-api-key"] = SEMANTIC_SCHOLAR_API_KEY
    return h


def _get(url: str, params: dict | None = None) -> dict | None:
    for attempt in range(MAX_RETRIES):
        try:
            with httpx.Client(headers=_headers(), timeout=15) as client:
                resp = client.get(url, params=params)
                if resp.status_code == 404:
                    return None
                if resp.status_code == 200:
                    return resp.json()
                if resp.status_code >= 500:
                    raise httpx.HTTPStatusError(f"{resp.status_code}", request=resp.request, response=resp)
                resp.raise_for_status()
        except (httpx.TimeoutException, httpx.HTTPStatusError, httpx.NetworkError):
            if attempt < MAX_RETRIES - 1:
                time.sleep(RETRY_BACKOFF_BASE * (2 ** attempt))
            else:
                raise
    return None


def search_semantic_scholar(title: str, limit: int = 5) -> list[dict]:
    params = {
        "query": title,
        "limit": limit,
        "fields": "title,authors,year,externalIds,venue",
    }
    result = _get(f"{BASE}/paper/search", params=params)
    if not result:
        return []
    items = []
    for p in result.get("data", []):
        doi = (p.get("externalIds") or {}).get("DOI", "")
        authors = [a.get("name", "").split()[-1] for a in (p.get("authors") or [])]
        items.append({
            "doi": doi,
            "title": p.get("title", ""),
            "authors": authors,
            "year": p.get("year"),
            "venue": p.get("venue"),
        })
    return items
