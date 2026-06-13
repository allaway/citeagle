from __future__ import annotations
import time
import httpx
from ..config import USER_AGENT, MAX_RETRIES, RETRY_BACKOFF_BASE


BASE = "https://api.crossref.org"


def _get(url: str, params: dict | None = None) -> dict | None:
    headers = {"User-Agent": USER_AGENT}
    for attempt in range(MAX_RETRIES):
        try:
            with httpx.Client(headers=headers, timeout=15) as client:
                resp = client.get(url, params=params)
                if resp.status_code == 404:
                    return None
                if resp.status_code == 200:
                    return resp.json()
                # 5xx — retry
                if resp.status_code >= 500:
                    raise httpx.HTTPStatusError(f"{resp.status_code}", request=resp.request, response=resp)
                resp.raise_for_status()
        except (httpx.TimeoutException, httpx.HTTPStatusError, httpx.NetworkError):
            if attempt < MAX_RETRIES - 1:
                time.sleep(RETRY_BACKOFF_BASE * (2 ** attempt))
            else:
                raise
    return None


def lookup_doi_crossref(doi: str) -> dict | None:
    """Return CrossRef work dict or None if not found. Raises on network error."""
    return _get(f"{BASE}/works/{doi}")


def search_crossref(title: str, author: str = "", rows: int = 5) -> list[dict]:
    """Return list of CrossRef work dicts from a bibliographic search."""
    params: dict = {"query.bibliographic": title, "rows": rows, "select": "DOI,title,author,published,container-title"}
    if author:
        params["query.author"] = author
    result = _get(f"{BASE}/works", params=params)
    if not result:
        return []
    return result.get("message", {}).get("items", [])
