from __future__ import annotations
import json
from dataclasses import asdict
from pathlib import Path
from .models import PreprintReport, Verdict


STATUS_ORDER = ["fabricated_doi", "doi_mismatch", "unverified", "needs_review", "metadata_error", "error", "verified"]


def _verdict_to_dict(v: Verdict) -> dict:
    d = asdict(v)
    return d


def write_json(report: PreprintReport, out_dir: Path) -> Path:
    out_dir.mkdir(parents=True, exist_ok=True)
    path = out_dir / "report.json"
    data = {
        "preprint_id": report.preprint_id,
        "preprint_title": report.preprint_title,
        "preprint_url": report.preprint_url,
        "counts": report.counts,
        "flagged_count": report.flagged_count,
        "total_count": report.total_count,
        "verdicts": [_verdict_to_dict(v) for v in report.verdicts],
    }
    path.write_text(json.dumps(data, indent=2))
    return path


def write_markdown(report: PreprintReport, out_dir: Path) -> Path:
    out_dir.mkdir(parents=True, exist_ok=True)
    path = out_dir / "report.md"
    lines: list[str] = []
    lines.append(f"# citeagle Report")
    lines.append("")
    if report.preprint_title:
        lines.append(f"**Preprint:** {report.preprint_title}")
    if report.preprint_url:
        lines.append(f"**URL:** {report.preprint_url}")
    lines.append(f"**ID:** {report.preprint_id}")
    lines.append("")

    # Summary table
    lines.append("## Summary")
    lines.append("")
    lines.append("| Status | Count |")
    lines.append("|--------|-------|")
    for status in STATUS_ORDER:
        if status in report.counts:
            lines.append(f"| `{status}` | {report.counts[status]} |")
    lines.append(f"| **Total** | **{report.total_count}** |")
    lines.append(f"| **Flagged** | **{report.flagged_count}** |")
    lines.append("")

    # Group verdicts by status
    by_status: dict[str, list[Verdict]] = {}
    for v in report.verdicts:
        by_status.setdefault(v.status, []).append(v)

    for status in STATUS_ORDER:
        verdicts = by_status.get(status, [])
        if not verdicts:
            continue
        lines.append(f"## {status.replace('_', ' ').title()} ({len(verdicts)})")
        lines.append("")
        for i, v in enumerate(verdicts, 1):
            lines.append(f"### {i}. {v.reference.title or '(no title)'}")
            lines.append(f"- **Raw:** {v.reference.raw[:200]}")
            lines.append(f"- **DOI:** {v.reference.doi or '—'}")
            lines.append(f"- **Status:** `{v.status}`")
            if v.matched_title:
                lines.append(f"- **Matched:** {v.matched_title}")
            if v.title_similarity:
                lines.append(f"- **Similarity:** {v.title_similarity:.2f}")
            lines.append(f"- **Source:** {v.source or '—'}")
            lines.append(f"- **Notes:** {v.notes}")
            lines.append("")

    path.write_text("\n".join(lines))
    return path
