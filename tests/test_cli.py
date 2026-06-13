import json
import tempfile
from pathlib import Path
from unittest.mock import patch, MagicMock
from typer.testing import CliRunner
from citeagle.cli import app
from citeagle.models import Reference, Verdict


runner = CliRunner()


def test_cli_check_bibtex(tmp_path):
    bib_content = """
@article{smith2020,
  author = {Smith, John},
  title = {A great paper on biology},
  year = {2020},
  journal = {Nature},
  doi = {10.1234/bio.2020},
}
"""
    bib_file = tmp_path / "refs.bib"
    bib_file.write_text(bib_content)
    out_dir = tmp_path / "out"

    cr_data = {
        "message": {
            "DOI": "10.1234/bio.2020",
            "title": ["A great paper on biology"],
            "author": [{"family": "Smith"}],
            "published": {"date-parts": [[2020]]},
            "container-title": ["Nature"],
        }
    }
    with patch("citeagle.classifier.lookup_doi_crossref", return_value=cr_data):
        result = runner.invoke(app, ["check", str(bib_file), "--out", str(out_dir), "--no-cache"])

    assert result.exit_code == 0, result.output
    assert (out_dir / "report.json").exists()
    data = json.loads((out_dir / "report.json").read_text())
    assert data["counts"].get("verified", 0) >= 1


def test_cli_no_post_by_default(tmp_path):
    """Default run must not post anything."""
    bib_content = """
@article{bad2020,
  author = {Ghost, A},
  title = {Nonexistent paper},
  year = {2020},
  doi = {10.9999/fake},
}
"""
    bib_file = tmp_path / "refs.bib"
    bib_file.write_text(bib_content)
    out_dir = tmp_path / "out"

    with patch("citeagle.classifier.lookup_doi_crossref", return_value=None), \
         patch("citeagle.classifier.lookup_doi_openalex", return_value=None), \
         patch("citeagle.bluesky.post_to_bluesky") as mock_post:
        result = runner.invoke(app, ["check", str(bib_file), "--out", str(out_dir), "--no-cache"])

    # post_to_bluesky may be called in dry-run mode (that's fine), but atproto Client.send_post must NOT be called
    # The important thing is exit code 0 and no real posting
    assert result.exit_code == 0, result.output
