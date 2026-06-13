from __future__ import annotations
import re
from ..models import Reference
from ..config import ANTHROPIC_API_KEY


_DOI_RE = re.compile(r"10\.\d{4,9}/[^\s,;\"'\]>]+", re.IGNORECASE)
_YEAR_RE = re.compile(r"\b(19|20)\d{2}\b")


def _heuristic_parse(lines: list[str]) -> list[Reference]:
    refs: list[Reference] = []
    for line in lines:
        line = line.strip()
        if not line:
            continue
        # strip leading number / bracket markers  e.g. "[1]" or "1."
        cleaned = re.sub(r"^\[?\d+[\]\.]\s*", "", line)

        doi_match = _DOI_RE.search(cleaned)
        doi = doi_match.group(0).rstrip(".,;") if doi_match else None

        year_match = _YEAR_RE.search(cleaned)
        year = int(year_match.group(0)) if year_match else None

        # rough title extraction: text between first "." or "," after author and next "."
        # This is intentionally simple — good enough for most numbered reference lists
        title: str | None = None
        parts = re.split(r"\.\s+", cleaned, maxsplit=3)
        if len(parts) >= 2:
            title = parts[1].strip() if len(parts[1]) > 10 else (parts[2].strip() if len(parts) > 2 else None)

        # authors: everything before the first year
        authors: list[str] = []
        if year_match:
            author_block = cleaned[: year_match.start()].strip().rstrip("(,.")
            # split on " and " or ","
            raw_names = re.split(r",\s*|\s+and\s+", author_block)
            for n in raw_names:
                n = n.strip()
                if n and len(n) > 1:
                    # take last word as surname
                    authors.append(n.split()[-1])

        refs.append(Reference(raw=line, authors=authors, title=title, year=year, doi=doi))
    return refs


def _llm_parse(text: str) -> list[Reference]:
    try:
        import anthropic
    except ImportError:
        return []

    client = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)
    prompt = (
        "Parse the following reference list into JSON. "
        "Return a JSON array where each item has keys: "
        "raw (original string), authors (list of surnames), title, year (int or null), venue, doi. "
        "Do not fabricate data; leave fields null if unknown.\n\n"
        f"References:\n{text}"
    )
    msg = client.messages.create(
        model="claude-sonnet-4-6",
        max_tokens=4096,
        messages=[{"role": "user", "content": prompt}],
    )
    raw_json = msg.content[0].text.strip()
    # extract JSON array
    m = re.search(r"\[.*\]", raw_json, re.DOTALL)
    if not m:
        return []
    import json
    items = json.loads(m.group(0))
    refs: list[Reference] = []
    for item in items:
        refs.append(Reference(
            raw=item.get("raw", ""),
            authors=item.get("authors") or [],
            title=item.get("title"),
            year=item.get("year"),
            venue=item.get("venue"),
            doi=item.get("doi"),
        ))
    return refs


def parse_plaintext(path: str) -> list[Reference]:
    text = open(path, encoding="utf-8", errors="replace").read()
    lines = [l for l in text.splitlines() if l.strip()]

    if ANTHROPIC_API_KEY:
        try:
            refs = _llm_parse(text)
            if refs:
                return refs
        except Exception:
            pass  # fall back to heuristic

    return _heuristic_parse(lines)
