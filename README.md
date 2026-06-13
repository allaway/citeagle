# citeagle 🦅

Eagle-eyed citation checker for scholarly preprints. `citeagle` audits the reference list of a bioRxiv/medRxiv preprint (or any BibTeX / plaintext reference list) for fabricated, hallucinated, or mismatched citations, and can publish a factual, evidence-based summary to Bluesky.

## Installation

```bash
# With uv (recommended)
uv pip install -e .

# Or with pip
pip install -e .
```

## Environment Variables

| Variable | Required | Description |
|---|---|---|
| `CITEAGLE_CONTACT_EMAIL` | Recommended | Used in API User-Agent for polite pool access |
| `BLUESKY_HANDLE` | For `--post` | Your Bluesky handle (e.g. `yourbot.bsky.social`) |
| `BLUESKY_APP_PASSWORD` | For `--post` | App password (not account password). Generate in Bluesky Settings → App Passwords |
| `ANTHROPIC_API_KEY` | Optional | Enables LLM-based reference parsing for `.txt` files |
| `SEMANTIC_SCHOLAR_API_KEY` | Optional | Improves lookup coverage with Semantic Scholar |

Copy `.env.example` to `.env` and fill in your values.

## Bluesky App Password

1. Log in to Bluesky (bsky.social)
2. Go to **Settings → App Passwords**
3. Click **Add App Password**, name it `citeagle`
4. Copy the generated password into `BLUESKY_APP_PASSWORD`

**Important:** Mark your posting account as a bot in Bluesky settings (Settings → Edit profile → check "This is an automated/bot account").

## Usage

### Dry run (default — no posting)

```bash
# Check a bioRxiv preprint by DOI
citeagle check 10.1101/2024.01.15.575432

# Check a BibTeX file
citeagle check references.bib

# Check a plaintext reference list
citeagle check references.txt

# Use Semantic Scholar as an additional source
citeagle check references.bib --semantic-scholar

# Custom output directory
citeagle check references.bib --out results/
```

### Post to Bluesky

```bash
# Post (with interactive confirmation)
citeagle check 10.1101/2024.01.15.575432 --post

# Post without confirmation (for scripted use)
citeagle check 10.1101/2024.01.15.575432 --post --yes

# Only post if at least 3 references are flagged
citeagle check references.bib --post --threshold 3
```

## Reference Retrieval Chain (for DOI inputs)

1. **Europe PMC** (preferred) — already-structured references, often with DOIs
2. **bioRxiv/medRxiv HTML full text** — parsed from the reference list section
3. **PDF** — not yet implemented (provide a `.bib` or `.txt` file instead)

The actual source used is logged to the terminal on each run.

## Classification

| Status | Meaning | Counts as flagged? |
|---|---|---|
| `verified` | DOI resolves and title/author/year match | No |
| `metadata_error` | Real paper, minor discrepancy (wrong year/venue) | No — never posted |
| `needs_review` | Similarity is ambiguous | No |
| `doi_mismatch` | DOI resolves to a different work | Yes |
| `fabricated_doi` | DOI does not exist | Yes |
| `unverified` | No DOI and no matching paper found | Yes |
| `error` | Transient network error | No — never posted |

## Output

Reports are written to `./out/` (or `--out DIR`):
- `report.json` — machine-readable full report
- `report.md` — human-readable summary table + per-reference details

## Limitations and False Positives

**This tool is automated and will make mistakes.** Treat its output as a starting point for human review, not a final verdict.

Known sources of false positives and negatives:

- **`unverified` ≠ hallucinated.** Many real papers are not indexed by CrossRef or OpenAlex, especially older works, non-English publications, and conference proceedings. An `unverified` result means the tool couldn't confirm the reference, not that the reference is fabricated.
- **`metadata_error` ≠ misconduct.** Wrong year or venue is common in good-faith citations (preprint vs. published version, year of online publication vs. print, etc.).
- **Title normalization is imperfect.** Subtitle formatting, special characters, and HTML entities can reduce similarity scores.
- **Author comparison is limited.** The tool compares only first-author surnames; author ordering or name formatting differences can cause false author mismatches.
- **DOI resolution depends on database coverage.** Some legitimate DOIs are not yet in CrossRef or OpenAlex.
- **Bluesky posts include an explicit disclaimer** that the check is automated and may contain errors.

**Never use `citeagle` output to make or imply accusations of misconduct without independent human expert review.**

## Development

```bash
pip install -e ".[dev]"
pytest
```

## License

MIT
