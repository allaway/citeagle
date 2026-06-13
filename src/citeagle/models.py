from __future__ import annotations
from dataclasses import dataclass, field, asdict
from typing import Any


@dataclass
class Reference:
    raw: str
    authors: list[str] = field(default_factory=list)
    title: str | None = None
    year: int | None = None
    venue: str | None = None
    doi: str | None = None


@dataclass
class Verdict:
    reference: Reference
    status: str  # verified | metadata_error | needs_review | doi_mismatch | fabricated_doi | unverified | error
    matched_title: str | None = None
    matched_doi: str | None = None
    title_similarity: float = 0.0
    source: str | None = None  # crossref | openalex | semantic_scholar | doi | None
    notes: str = ""

    def to_dict(self) -> dict[str, Any]:
        d = asdict(self)
        return d


@dataclass
class PreprintReport:
    preprint_id: str
    preprint_title: str | None
    preprint_url: str | None
    verdicts: list[Verdict]
    counts: dict[str, int] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not self.counts:
            self._recount()

    def _recount(self) -> None:
        self.counts = {}
        for v in self.verdicts:
            self.counts[v.status] = self.counts.get(v.status, 0) + 1

    @property
    def flagged_count(self) -> int:
        return sum(self.counts.get(s, 0) for s in ("doi_mismatch", "fabricated_doi", "unverified"))

    @property
    def total_count(self) -> int:
        return len(self.verdicts)
