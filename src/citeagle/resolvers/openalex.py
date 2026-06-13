from __future__ import annotations
import time
import httpx
from ..config import USER_AGENT, MAX_RETRIES, RETRY_BACKOFF_BASE


BASE = "https://api.openalex.org"


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
                if resp.status_code >= 500:
                    raise httpx.HTTPStatusError(f"{resp.status_code}", request=resp.request, response=resp)
                resp.raise_for_status()
        except (httpx.TimeoutException, httpx.HTTPStatusError, httpx.NetworkError):
            if attempt < MAX_RETRIES - 1:
                time.sleep(RETRY_BACKOFF_BASE * (2 ** attempt))
            else:
                raise
    return None


def _extract_work(item: dict) -> dict:
    """Normalize an OpenAlex work to a common shape."""
    doi = item.get("doi") or ""
    doi = doi.replace("https://doi.org/", "").strip()
    title = item.get("display_name") or ""
    authors = []
    for auth in (item.get("authorships") or []):
        author_obj = auth.get("author") or {}
        display = author_obj.get("display_name", "")
        if display:
            authors.append(display.split()[-1])  # surname
    pub_year = item.get("publication_year")
    venue_obj = item.get("primary_location") or {}
    source_obj = venue_obj.get("source") or {}
    venue = source_obj.get("display_name")
    return {"doi": doi, "title": title, "authors": authors, "year": pub_year, "venue": venue}


def lookup_doi_openalex(doi: str) -> dict | None:
    """Return normalized work dict or None."""
    result = _get(f"{BASE}/works/doi:{doi}")
    if not result:
        return None
    return _extract_work(result)


def search_openalex(title: str, per_page: int = 5) -> list[dict]:
    """Return list of normalized work dicts."""
    params = {"search": title, "per_page": per_page}
    result = _get(f"{BASE}/works", params=params)
    if not result:
        return []
    return [_extract_work(w) for w in result.get("results", [])]
