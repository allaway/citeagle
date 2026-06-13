from __future__ import annotations
import re
import bibtexparser
from bibtexparser.bparser import BibTexParser
from bibtexparser.customization import convert_to_unicode, author
from ..models import Reference


def _normalize_doi(doi: str | None) -> str | None:
    if not doi:
        return None
    doi = doi.strip().rstrip(".")
    # strip URL prefix
    doi = re.sub(r"^https?://(dx\.)?doi\.org/", "", doi, flags=re.IGNORECASE)
    return doi or None


def _extract_surnames(author_string: str) -> list[str]:
    names = [n.strip() for n in author_string.split(" and ") if n.strip()]
    surnames: list[str] = []
    for name in names:
        if "," in name:
            surnames.append(name.split(",")[0].strip())
        else:
            parts = name.split()
            if parts:
                surnames.append(parts[-1])
    return surnames


def parse_bibtex(path: str) -> list[Reference]:
    parser = BibTexParser(common_strings=True)
    parser.customization = convert_to_unicode
    with open(path, encoding="utf-8", errors="replace") as fh:
        bib = bibtexparser.load(fh, parser=parser)

    refs: list[Reference] = []
    for entry in bib.entries:
        title = entry.get("title", "").strip("{} \n")
        raw_author = entry.get("author", "")
        surnames = _extract_surnames(raw_author) if raw_author else []
        year_str = entry.get("year", "")
        year: int | None = None
        try:
            year = int(year_str)
        except (ValueError, TypeError):
            pass
        venue = entry.get("journal") or entry.get("booktitle") or entry.get("publisher")
        doi = _normalize_doi(entry.get("doi"))
        raw = f"{raw_author} ({year_str}). {title}."
        refs.append(Reference(raw=raw, authors=surnames, title=title or None, year=year, venue=venue, doi=doi))
    return refs
