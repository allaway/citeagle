from __future__ import annotations
import re
import httpx
from ..models import Reference
from ..config import USER_AGENT


_DOI_RE = re.compile(r"10\.\d{4,9}/[^\s,;\"'\]>]+", re.IGNORECASE)


def _clean_doi(doi: str | None) -> str | None:
    if not doi:
        return None
    doi = re.sub(r"^https?://(dx\.)?doi\.org/", "", doi.strip(), flags=re.IGNORECASE)
    return doi.rstrip(".,;") or None


def _to_reference(epmc_ref: dict) -> Reference:
    title = epmc_ref.get("title") or epmc_ref.get("citedTitle") or None
    if title:
        title = title.strip()

    author_list = epmc_ref.get("authorList", {}).get("author", []) or []
    authors = [a.get("lastName", a.get("fullName", "")).strip() for a in author_list if a]
    authors = [a for a in authors if a]

    # fallback: parse from authorString
    if not authors:
        author_str = epmc_ref.get("authorString", "")
        for name in re.split(r",\s*|\s+and\s+", author_str):
            n = name.strip()
            if n:
                authors.append(n.split()[-1])

    year_str = epmc_ref.get("pubYear") or epmc_ref.get("year") or ""
    year: int | None = None
    try:
        year = int(str(year_str))
    except (ValueError, TypeError):
        pass

    doi = _clean_doi(epmc_ref.get("doi") or epmc_ref.get("DOI"))
    venue = epmc_ref.get("journalAbbreviation") or epmc_ref.get("journal") or None

    raw = epmc_ref.get("referenceString") or f"{epmc_ref.get('authorString', '')} ({year_str}). {title}."
    return Reference(raw=raw, authors=authors, title=title, year=year, venue=venue, doi=doi)


def _epmc_search_preprint(doi: str, client: httpx.Client) -> tuple[str, str] | None:
    """Return (source, id) for the preprint in Europe PMC."""
    url = f"https://www.ebi.ac.uk/europepmc/webservices/rest/search?query=DOI:{doi}&format=json&pageSize=5"
    resp = client.get(url, timeout=20)
    resp.raise_for_status()
    data = resp.json()
    results = data.get("resultList", {}).get("result", [])
    for r in results:
        # Prefer PPR (preprint) source but accept any
        if r.get("doi", "").lower() == doi.lower() or r.get("DOI", "").lower() == doi.lower():
            return r.get("source", "PPR"), r.get("id", "")
    if results:
        return results[0].get("source", "PPR"), results[0].get("id", "")
    return None


def _epmc_fetch_references(source: str, epmc_id: str, client: httpx.Client) -> list[Reference]:
    url = f"https://www.ebi.ac.uk/europepmc/webservices/rest/{source}/{epmc_id}/references?format=json&pageSize=1000"
    resp = client.get(url, timeout=30)
    resp.raise_for_status()
    data = resp.json()
    ref_list = data.get("referenceList", {}).get("reference", []) or []
    return [_to_reference(r) for r in ref_list]


def _fetch_biorxiv_fulltext_refs(doi: str, client: httpx.Client) -> list[Reference]:
    """Try to get HTML full text from bioRxiv/medRxiv and parse reference section."""
    for server in ("biorxiv", "medrxiv"):
        url = f"https://www.{server}.org/content/{doi}"
        try:
            resp = client.get(url, follow_redirects=True, timeout=30)
            if resp.status_code != 200:
                continue
            html = resp.text
            # Find reference section
            ref_section = re.search(
                r'<ol[^>]*class="[^"]*ref-list[^"]*"[^>]*>(.*?)</ol>',
                html, re.DOTALL | re.IGNORECASE
            )
            if not ref_section:
                ref_section = re.search(
                    r'<div[^>]*class="[^"]*references[^"]*"[^>]*>(.*?)</div>\s*(?=<div|<section)',
                    html, re.DOTALL | re.IGNORECASE
                )
            if not ref_section:
                continue
            raw_html = ref_section.group(1)
            items = re.findall(r"<li[^>]*>(.*?)</li>", raw_html, re.DOTALL | re.IGNORECASE)
            if not items:
                items = re.findall(r"<p[^>]*>(.*?)</p>", raw_html, re.DOTALL | re.IGNORECASE)
            refs: list[Reference] = []
            for item in items:
                text = re.sub(r"<[^>]+>", " ", item)
                text = re.sub(r"\s+", " ", text).strip()
                if len(text) < 20:
                    continue
                doi_match = _DOI_RE.search(text)
                ref_doi = _clean_doi(doi_match.group(0)) if doi_match else None
                year_match = re.search(r"\b(19|20)\d{2}\b", text)
                year = int(year_match.group(0)) if year_match else None
                refs.append(Reference(raw=text, authors=[], title=None, year=year, doi=ref_doi))
            if refs:
                return refs
        except Exception:
            continue
    return []


def fetch_references_for_doi(doi: str) -> tuple[list[Reference], str]:
    """Return (references, source_description). Tries EPMC -> fulltext."""
    headers = {"User-Agent": USER_AGENT}
    with httpx.Client(headers=headers) as client:
        # 1. Try Europe PMC
        try:
            loc = _epmc_search_preprint(doi, client)
            if loc:
                source, epmc_id = loc
                refs = _epmc_fetch_references(source, epmc_id, client)
                if refs:
                    return refs, f"Europe PMC ({source}/{epmc_id})"
        except Exception:
            pass

        # 2. Try bioRxiv/medRxiv full text
        refs = _fetch_biorxiv_fulltext_refs(doi, client)
        if refs:
            return refs, "bioRxiv/medRxiv full text HTML"

    return [], "none"
