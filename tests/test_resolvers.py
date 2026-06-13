"""Smoke tests for resolver modules — these mock the HTTP layer."""
import pytest
from unittest.mock import patch, MagicMock
import httpx


def make_mock_response(status_code: int, json_data: dict | None = None):
    mock = MagicMock(spec=httpx.Response)
    mock.status_code = status_code
    if json_data is not None:
        mock.json.return_value = json_data
    return mock


def test_lookup_doi_crossref_found():
    from citeagle.resolvers.crossref import lookup_doi_crossref
    payload = {"message": {"DOI": "10.1234/test", "title": ["Test Title"], "author": [], "container-title": []}}
    mock_resp = make_mock_response(200, payload)
    with patch("httpx.Client") as mock_client_cls:
        mock_client = MagicMock()
        mock_client.__enter__ = MagicMock(return_value=mock_client)
        mock_client.__exit__ = MagicMock(return_value=False)
        mock_client.get.return_value = mock_resp
        mock_client_cls.return_value = mock_client
        result = lookup_doi_crossref("10.1234/test")
    assert result is not None
    assert result["message"]["DOI"] == "10.1234/test"


def test_lookup_doi_crossref_not_found():
    from citeagle.resolvers.crossref import lookup_doi_crossref
    mock_resp = make_mock_response(404)
    with patch("httpx.Client") as mock_client_cls:
        mock_client = MagicMock()
        mock_client.__enter__ = MagicMock(return_value=mock_client)
        mock_client.__exit__ = MagicMock(return_value=False)
        mock_client.get.return_value = mock_resp
        mock_client_cls.return_value = mock_client
        result = lookup_doi_crossref("10.9999/nonexistent")
    assert result is None


def test_lookup_doi_openalex_found():
    from citeagle.resolvers.openalex import lookup_doi_openalex
    payload = {
        "doi": "https://doi.org/10.1234/test",
        "display_name": "Test Title",
        "authorships": [{"author": {"display_name": "John Smith"}}],
        "publication_year": 2020,
        "primary_location": {"source": {"display_name": "Nature"}},
    }
    mock_resp = make_mock_response(200, payload)
    with patch("httpx.Client") as mock_client_cls:
        mock_client = MagicMock()
        mock_client.__enter__ = MagicMock(return_value=mock_client)
        mock_client.__exit__ = MagicMock(return_value=False)
        mock_client.get.return_value = mock_resp
        mock_client_cls.return_value = mock_client
        result = lookup_doi_openalex("10.1234/test")
    assert result is not None
    assert result["title"] == "Test Title"
    assert result["doi"] == "10.1234/test"


def test_search_crossref_returns_list():
    from citeagle.resolvers.crossref import search_crossref
    payload = {"message": {"items": [{"DOI": "10.1/x", "title": ["A title"], "author": [], "container-title": []}]}}
    mock_resp = make_mock_response(200, payload)
    with patch("httpx.Client") as mock_client_cls:
        mock_client = MagicMock()
        mock_client.__enter__ = MagicMock(return_value=mock_client)
        mock_client.__exit__ = MagicMock(return_value=False)
        mock_client.get.return_value = mock_resp
        mock_client_cls.return_value = mock_client
        result = search_crossref("A title")
    assert isinstance(result, list)
    assert len(result) == 1
