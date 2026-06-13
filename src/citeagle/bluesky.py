from __future__ import annotations
import unicodedata
from .models import PreprintReport
from .config import BLUESKY_HANDLE, BLUESKY_APP_PASSWORD


POSTABLE_STATUSES = {"doi_mismatch", "fabricated_doi", "unverified"}
DISCLAIMER = "Automated check, may contain errors."
FOOTER = "🦅 citeagle"
MAX_GRAPHEMES = 300


def _grapheme_len(s: str) -> int:
    # Simple approximation: each code point is one grapheme
    # For full grapheme cluster support, use the `grapheme` library
    return len(s)


def _count_graphemes(s: str) -> int:
    return _grapheme_len(s)


def _build_body(title: str, url: str, flagged: int, total: int,
                fabricated: int, mismatch: int, unverified: int) -> str:
    return (
        f"Automated reference check — {title} ({url}): "
        f"{flagged} of {total} references could not be verified against CrossRef/OpenAlex "
        f"({fabricated} nonexistent DOIs, {mismatch} DOIs resolving to a different work, "
        f"{unverified} with no matching record found). "
        f"{DISCLAIMER}"
    )


def build_post_text(report: PreprintReport) -> str:
    counts = report.counts
    fabricated = counts.get("fabricated_doi", 0)
    mismatch = counts.get("doi_mismatch", 0)
    unverified = counts.get("unverified", 0)
    flagged = fabricated + mismatch + unverified
    total = report.total_count

    url = report.preprint_url or report.preprint_id
    title = report.preprint_title or report.preprint_id

    body = _build_body(title, url, flagged, total, fabricated, mismatch, unverified)

    # Truncate title if body exceeds the grapheme limit
    if _count_graphemes(body) > MAX_GRAPHEMES:
        # Binary-search a shorter title that fits
        for cut in range(len(title) - 1, 0, -1):
            short_title = title[:cut].rstrip() + "…"
            candidate = _build_body(short_title, url, flagged, total, fabricated, mismatch, unverified)
            if _count_graphemes(candidate) <= MAX_GRAPHEMES:
                body = candidate
                break

    with_footer = body + f"\n{FOOTER}"
    if _count_graphemes(with_footer) <= MAX_GRAPHEMES:
        return with_footer
    return body


def should_post(report: PreprintReport, threshold: int) -> bool:
    return report.flagged_count >= threshold


def post_to_bluesky(text: str, dry_run: bool = True, yes: bool = False) -> None:
    print("\n--- Bluesky post preview ---")
    print(text)
    print(f"--- ({_count_graphemes(text)} graphemes) ---\n")

    if dry_run:
        print("[dry run] Post NOT sent. Pass --post to enable posting.")
        return

    if not yes:
        confirm = input("Post this to Bluesky? [y/N] ").strip().lower()
        if confirm != "y":
            print("Aborted.")
            return

    if not BLUESKY_HANDLE or not BLUESKY_APP_PASSWORD:
        raise ValueError("BLUESKY_HANDLE and BLUESKY_APP_PASSWORD env vars must be set.")

    try:
        from atproto import Client
    except ImportError:
        raise ImportError("atproto is required for Bluesky posting: pip install atproto")

    client = Client()
    client.login(BLUESKY_HANDLE, BLUESKY_APP_PASSWORD)
    client.send_post(text=text)
    print("Posted to Bluesky successfully.")
