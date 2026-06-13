from __future__ import annotations
import sys
from pathlib import Path
import typer
from .cache import Cache
from .classifier import classify
from .models import PreprintReport
from .reporter import write_json, write_markdown
from .bluesky import build_post_text, should_post, post_to_bluesky

app = typer.Typer(help="citeagle — eagle-eyed citation checker for scholarly preprints.")


@app.command()
def check(
    input_arg: str = typer.Argument(..., metavar="INPUT", help=".bib | .txt | DOI | URL"),
    pdf: Path | None = typer.Option(None, "--pdf", help="PDF to extract references from"),
    post: bool = typer.Option(False, "--post", help="Enable Bluesky posting"),
    yes: bool = typer.Option(False, "--yes", help="Skip confirmation prompt"),
    threshold: int = typer.Option(1, "--threshold", help="Min flagged references required to post"),
    semantic_scholar: bool = typer.Option(False, "--semantic-scholar", help="Use Semantic Scholar as additional source"),
    out: Path = typer.Option(Path("out"), "--out", help="Output directory"),
    no_cache: bool = typer.Option(False, "--no-cache", help="Bypass lookup cache"),
) -> None:
    """Check references in a preprint for fabrications and mismatches."""

    cache = Cache(disabled=no_cache)

    refs = []
    preprint_title: str | None = None
    preprint_url: str | None = None
    source_log: str = ""

    input_path = Path(input_arg)

    if input_path.exists() and input_path.suffix.lower() == ".bib":
        typer.echo(f"Parsing BibTeX file: {input_path}")
        from .parsers.bibtex import parse_bibtex
        refs = parse_bibtex(str(input_path))
        source_log = f".bib file: {input_path}"
        preprint_title = input_path.stem

    elif input_path.exists() and input_path.suffix.lower() in (".txt", ".text"):
        typer.echo(f"Parsing plaintext reference list: {input_path}")
        from .parsers.plaintext import parse_plaintext
        refs = parse_plaintext(str(input_path))
        source_log = f"plaintext file: {input_path}"
        preprint_title = input_path.stem

    elif pdf is not None:
        typer.echo(f"PDF input not yet implemented; use a .bib or .txt file.")
        raise typer.Exit(1)

    else:
        # Treat as DOI / URL
        doi = input_arg.strip()
        import re
        doi = re.sub(r"^https?://(dx\.)?doi\.org/", "", doi)
        doi = re.sub(r"^https?://www\.(biorxiv|medrxiv)\.org/content/", "", doi)
        doi = doi.rstrip("/v1 /v2 /v3 /v4 /v5".split())
        # strip version suffixes
        doi = re.sub(r"v\d+$", "", doi)

        typer.echo(f"Fetching references for DOI: {doi}")
        from .parsers.epmc import fetch_references_for_doi
        refs, source_log = fetch_references_for_doi(doi)
        typer.echo(f"Reference source: {source_log}")
        preprint_url = f"https://doi.org/{doi}"
        preprint_title = doi

        # Try to get preprint title from bioRxiv API
        try:
            import httpx
            from .config import USER_AGENT
            for server in ("biorxiv", "medrxiv"):
                r = httpx.get(
                    f"https://api.biorxiv.org/details/{server}/{doi}",
                    headers={"User-Agent": USER_AGENT},
                    timeout=10,
                )
                if r.status_code == 200:
                    collection = r.json().get("collection") or []
                    if collection:
                        preprint_title = collection[0].get("title", doi)
                        break
        except Exception:
            pass

    if not refs:
        typer.echo("No references found.", err=True)
        raise typer.Exit(1)

    typer.echo(f"Verifying {len(refs)} references...")

    verdicts = []
    for i, ref in enumerate(refs, 1):
        v = classify(ref, cache, use_semantic=semantic_scholar)
        verdicts.append(v)
        status_sym = {"verified": "✓", "fabricated_doi": "✗", "doi_mismatch": "≠",
                      "unverified": "?", "metadata_error": "~", "needs_review": "·", "error": "!"}.get(v.status, " ")
        typer.echo(f"  [{i}/{len(refs)}] {status_sym} {v.status:16s} {ref.title or ref.raw[:60]}")

    report = PreprintReport(
        preprint_id=input_arg,
        preprint_title=preprint_title,
        preprint_url=preprint_url,
        verdicts=verdicts,
    )

    json_path = write_json(report, out)
    md_path = write_markdown(report, out)
    typer.echo(f"\nReport written to: {json_path}, {md_path}")
    typer.echo(f"Summary: {report.counts}")
    typer.echo(f"Flagged: {report.flagged_count} of {report.total_count}")

    # Bluesky
    post_text = build_post_text(report)
    if post:
        if should_post(report, threshold):
            post_to_bluesky(post_text, dry_run=False, yes=yes)
        else:
            typer.echo(f"Flagged count ({report.flagged_count}) below threshold ({threshold}). Not posting.")
    else:
        if should_post(report, threshold):
            post_to_bluesky(post_text, dry_run=True)


if __name__ == "__main__":
    app()
