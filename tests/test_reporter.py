import json
import tempfile
from pathlib import Path
from citeagle.models import Reference, Verdict, PreprintReport
from citeagle.reporter import write_json, write_markdown


def make_report():
    ref = Reference(raw="Smith J (2020). A paper.", authors=["Smith"], title="A paper", year=2020, doi="10.1/test")
    v = Verdict(reference=ref, status="verified", notes="ok", title_similarity=0.95, source="crossref")
    return PreprintReport(preprint_id="test", preprint_title="Test Preprint", preprint_url="https://doi.org/test", verdicts=[v])


def test_write_json():
    with tempfile.TemporaryDirectory() as tmp:
        path = write_json(make_report(), Path(tmp))
        data = json.loads(path.read_text())
        assert data["preprint_id"] == "test"
        assert "verdicts" in data
        assert data["counts"]["verified"] == 1


def test_write_markdown():
    with tempfile.TemporaryDirectory() as tmp:
        path = write_markdown(make_report(), Path(tmp))
        text = path.read_text()
        assert "citeagle Report" in text
        assert "verified" in text.lower()
