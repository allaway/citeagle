import pytest
from unittest.mock import patch, MagicMock
from citeagle.models import Reference
from citeagle.cache import Cache
from citeagle.classifier import classify


def make_cache():
    return Cache(disabled=True)


def crossref_response(doi, title, authors, year):
    return {
        "message": {
            "DOI": doi,
            "title": [title],
            "author": [{"family": a} for a in authors],
            "published": {"date-parts": [[year]]},
            "container-title": ["Nature"],
        }
    }


def test_verified_doi():
    ref = Reference(
        raw="Smith J (2020). A great paper on biology.",
        authors=["Smith"],
        title="A great paper on biology",
        year=2020,
        doi="10.1234/bio.2020",
    )
    cr_data = crossref_response("10.1234/bio.2020", "A great paper on biology", ["Smith"], 2020)
    with patch("citeagle.classifier.lookup_doi_crossref", return_value=cr_data):
        v = classify(ref, make_cache())
    assert v.status == "verified"
    assert v.title_similarity >= 0.9


def test_fabricated_doi():
    ref = Reference(
        raw="Nobody N (2099). Imaginary paper.",
        authors=["Nobody"],
        title="Imaginary paper",
        year=2099,
        doi="10.9999/does-not-exist",
    )
    with patch("citeagle.classifier.lookup_doi_crossref", return_value=None), \
         patch("citeagle.classifier.lookup_doi_openalex", return_value=None):
        v = classify(ref, make_cache())
    assert v.status == "fabricated_doi"


def test_doi_mismatch():
    ref = Reference(
        raw="Smith J (2020). Biology paper.",
        authors=["Smith"],
        title="Biology paper",
        year=2020,
        doi="10.1234/chemistry.2018",
    )
    cr_data = crossref_response("10.1234/chemistry.2018", "Introduction to organic chemistry reactions", ["Brown"], 2018)
    with patch("citeagle.classifier.lookup_doi_crossref", return_value=cr_data):
        v = classify(ref, make_cache())
    assert v.status == "doi_mismatch"


def test_metadata_error_wrong_year():
    ref = Reference(
        raw="Smith J (2021). A great paper on biology.",
        authors=["Smith"],
        title="A great paper on biology",
        year=2021,
        doi="10.1234/bio.2020",
    )
    cr_data = crossref_response("10.1234/bio.2020", "A great paper on biology", ["Smith"], 2020)
    with patch("citeagle.classifier.lookup_doi_crossref", return_value=cr_data):
        v = classify(ref, make_cache())
    # year differs by more than 1 (2021 vs 2020 is exactly 1, so boundary case — let's use 2022)
    ref.year = 2022
    with patch("citeagle.classifier.lookup_doi_crossref", return_value=cr_data):
        v = classify(ref, make_cache())
    assert v.status == "metadata_error"
    assert v.status != "fabricated_doi"
    assert v.status != "doi_mismatch"


def test_no_doi_verified():
    ref = Reference(
        raw="Jones B (2019). Methods in computational biology.",
        authors=["Jones"],
        title="Methods in computational biology",
        year=2019,
        doi=None,
    )
    cr_results = [crossref_response("10.9999/comp.2019", "Methods in computational biology", ["Jones"], 2019)]
    with patch("citeagle.classifier.search_crossref", return_value=cr_results), \
         patch("citeagle.classifier.search_openalex", return_value=[]):
        v = classify(ref, make_cache())
    assert v.status == "verified"


def test_no_doi_unverified():
    ref = Reference(
        raw="Ghost A (2020). Phantom results in nonexistent field.",
        authors=["Ghost"],
        title="Phantom results in nonexistent field",
        year=2020,
        doi=None,
    )
    with patch("citeagle.classifier.search_crossref", return_value=[]), \
         patch("citeagle.classifier.search_openalex", return_value=[]):
        v = classify(ref, make_cache())
    assert v.status == "unverified"


def test_transient_503_returns_error():
    import httpx
    ref = Reference(
        raw="Smith J (2020). A paper.",
        authors=["Smith"],
        title="A paper",
        year=2020,
        doi="10.1234/test",
    )
    with patch("citeagle.classifier.lookup_doi_crossref", side_effect=httpx.HTTPStatusError("503", request=MagicMock(), response=MagicMock(status_code=503))):
        v = classify(ref, make_cache())
    assert v.status == "error"
    assert v.status != "fabricated_doi"
