from __future__ import annotations
import re
import time
import httpx
from rapidfuzz import fuzz
from .models import Reference, Verdict
from .cache import Cache
from .config import (
    TITLE_SIM_VERIFIED, TITLE_SIM_NEEDS_REVIEW_LOWER, TITLE_SIM_MISMATCH,
    TITLE_SIM_NO_DOI_VERIFIED, TITLE_SIM_NO_DOI_NEEDS_REVIEW,
    MAX_RETRIES, RETRY_BACKOFF_BASE,
)
from .resolvers import lookup_doi_crossref, search_crossref, lookup_doi_openalex, search_openalex


def _normalize_text(s: str | None) -> str:
    if not s:
        return ""
    s = s.lower()
    s = re.sub(r"[^\w\s]", " ", s)
    s = re.sub(r"\s+", " ", s).strip()
    return s


def _title_sim(a: str | None, b: str | None) -> float:
    if not a or not b:
        return 0.0
    return fuzz.token_sort_ratio(_normalize_text(a), _normalize_text(b)) / 100.0


def _author_consistent(ref_authors: list[str], match_authors: list[str]) -> bool:
    if not ref_authors or not match_authors:
        return True  # can't compare, give benefit of doubt
    first_ref = _normalize_text(ref_authors[0])
    first_match = _normalize_text(match_authors[0])
    if not first_ref or not first_match:
        return True
    return fuzz.partial_ratio(first_ref, first_match) >= 70


def _year_consistent(ref_year: int | None, match_year: int | None) -> bool:
    if ref_year is None or match_year is None:
        return True  # can't compare, give benefit of doubt
    return abs(ref_year - match_year) <= 1  # allow 1-year off-by-one


def _crossref_to_common(cr: dict) -> dict:
    msg = cr.get("message", cr)  # handle wrapped or unwrapped
    title_list = msg.get("title") or []
    title = title_list[0] if title_list else ""
    authors = []
    for a in (msg.get("author") or []):
        surname = a.get("family") or a.get("name", "")
        if surname:
            authors.append(surname)
    pub = msg.get("published") or msg.get("published-print") or msg.get("published-online") or {}
    parts = pub.get("date-parts") or [[]]
    year = parts[0][0] if parts and parts[0] else None
    doi = msg.get("DOI", "")
    venue_list = msg.get("container-title") or []
    venue = venue_list[0] if venue_list else None
    return {"doi": doi, "title": title, "authors": authors, "year": year, "venue": venue}


def _classify_with_doi(ref: Reference, cache: Cache, use_semantic: bool) -> Verdict:
    doi = ref.doi
    cache_key = f"doi:{doi}"

    match_data = cache.get(cache_key)
    transient_error = False

    if match_data is None:
        # Try CrossRef
        try:
            cr = lookup_doi_crossref(doi)
            if cr:
                match_data = _crossref_to_common(cr)
                cache.set(cache_key, {"found": True, "source": "crossref", "data": match_data})
            else:
                # Try OpenAlex
                try:
                    oa = lookup_doi_openalex(doi)
                    if oa:
                        match_data = oa
                        cache.set(cache_key, {"found": True, "source": "openalex", "data": match_data})
                    else:
                        cache.set(cache_key, {"found": False})
                        match_data = None
                except Exception:
                    cache.set(cache_key, {"found": False})
                    match_data = None
        except (httpx.TimeoutException, httpx.HTTPStatusError, httpx.NetworkError):
            transient_error = True
    else:
        # cache hit — unwrap
        if isinstance(match_data, dict) and "found" in match_data:
            if not match_data["found"]:
                match_data = None
            else:
                source_tag = match_data.get("source", "crossref")
                match_data = match_data.get("data")
                if match_data:
                    match_data["_source"] = source_tag

    if transient_error:
        return Verdict(
            reference=ref,
            status="error",
            notes="Network/timeout error during DOI lookup; may resolve on retry.",
        )

    if match_data is None:
        return Verdict(
            reference=ref,
            status="fabricated_doi",
            notes=f"DOI {doi} returned 404 from CrossRef and OpenAlex.",
        )

    # We have a match — compare
    source = match_data.get("_source", "crossref")
    author_ok = _author_consistent(ref.authors, match_data.get("authors", []))
    year_ok = _year_consistent(ref.year, match_data.get("year"))

    # If the reference has no title we cannot compare titles — DOI resolved, so
    # it's not fabricated, but we can't confirm it's the right paper either.
    if not ref.title:
        return Verdict(
            reference=ref,
            status="needs_review",
            matched_title=match_data.get("title"),
            matched_doi=match_data.get("doi", doi),
            title_similarity=0.0,
            source=source,
            notes=f"DOI resolves to '{match_data.get('title')}' but reference has no title to compare.",
        )

    sim = _title_sim(ref.title, match_data.get("title"))

    if sim >= TITLE_SIM_VERIFIED:
        if author_ok and year_ok:
            status = "verified"
            notes = f"Title match {sim:.2f}, author and year consistent."
        else:
            status = "metadata_error"
            notes = (
                f"Title match {sim:.2f} but metadata mismatch: "
                f"author_ok={author_ok}, year_ok={year_ok} "
                f"(claimed {ref.year}, found {match_data.get('year')})."
            )
    elif sim < TITLE_SIM_MISMATCH:
        status = "doi_mismatch"
        notes = f"DOI resolves to a different work (title sim {sim:.2f})."
    else:
        status = "needs_review"
        notes = f"Title similarity {sim:.2f} is ambiguous."

    return Verdict(
        reference=ref,
        status=status,
        matched_title=match_data.get("title"),
        matched_doi=match_data.get("doi", doi),
        title_similarity=sim,
        source=source,
        notes=notes,
    )


def _classify_without_doi(ref: Reference, cache: Cache, use_semantic: bool) -> Verdict:
    if not ref.title:
        return Verdict(reference=ref, status="unverified", notes="No title or DOI; cannot verify.")

    cache_key = f"search:{_normalize_text(ref.title)}"
    cached = cache.get(cache_key)

    candidates: list[dict] = []
    if cached is not None:
        candidates = cached
    else:
        # CrossRef search
        first_author = ref.authors[0] if ref.authors else ""
        try:
            cr_results = search_crossref(ref.title, author=first_author)
            for item in cr_results:
                c = _crossref_to_common(item)
                c["_source"] = "crossref"
                candidates.append(c)
        except Exception:
            pass

        # OpenAlex search
        try:
            oa_results = search_openalex(ref.title)
            for item in oa_results:
                item["_source"] = "openalex"
                candidates.append(item)
        except Exception:
            pass

        # Semantic Scholar (optional)
        if use_semantic:
            try:
                from .resolvers.semantic import search_semantic_scholar
                ss_results = search_semantic_scholar(ref.title)
                for item in ss_results:
                    item["_source"] = "semantic_scholar"
                    candidates.append(item)
            except Exception:
                pass

        cache.set(cache_key, candidates)

    if not candidates:
        return Verdict(reference=ref, status="unverified", notes="No candidates found in CrossRef/OpenAlex.")

    best: dict | None = None
    best_sim = 0.0
    for c in candidates:
        s = _title_sim(ref.title, c.get("title"))
        if s > best_sim:
            best_sim = s
            best = c

    if best is None or best_sim < TITLE_SIM_NO_DOI_NEEDS_REVIEW:
        return Verdict(
            reference=ref,
            status="unverified",
            title_similarity=best_sim,
            matched_title=best.get("title") if best else None,
            notes=f"Best candidate similarity {best_sim:.2f} is below threshold.",
        )

    author_ok = _author_consistent(ref.authors, best.get("authors", []))
    year_ok = _year_consistent(ref.year, best.get("year"))

    if best_sim >= TITLE_SIM_NO_DOI_VERIFIED:
        if author_ok and year_ok:
            status = "verified"
        else:
            status = "metadata_error"
    else:
        status = "needs_review"

    return Verdict(
        reference=ref,
        status=status,
        matched_title=best.get("title"),
        matched_doi=best.get("doi") or None,
        title_similarity=best_sim,
        source=best.get("_source"),
        notes=(
            f"Best match sim={best_sim:.2f}, author_ok={author_ok}, year_ok={year_ok}. "
            f"Source: {best.get('_source')}."
        ),
    )


def classify(ref: Reference, cache: Cache, use_semantic: bool = False) -> Verdict:
    if ref.doi:
        return _classify_with_doi(ref, cache, use_semantic)
    return _classify_without_doi(ref, cache, use_semantic)
