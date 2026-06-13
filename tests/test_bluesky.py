from citeagle.models import Reference, Verdict, PreprintReport
from citeagle.bluesky import build_post_text, should_post, MAX_GRAPHEMES, _count_graphemes


def make_report(flagged_statuses=None, extra_statuses=None):
    ref = Reference(raw="test", authors=[], title="test", year=2020, doi="10.1/x")
    verdicts = []
    for s in (flagged_statuses or []):
        verdicts.append(Verdict(reference=ref, status=s, notes=""))
    for s in (extra_statuses or []):
        verdicts.append(Verdict(reference=ref, status=s, notes=""))
    return PreprintReport(
        preprint_id="10.1101/test",
        preprint_title="My Preprint",
        preprint_url="https://biorxiv.org/content/10.1101/test",
        verdicts=verdicts or [Verdict(reference=ref, status="verified", notes="")],
    )


def test_post_text_length():
    report = make_report(["fabricated_doi", "doi_mismatch"], ["verified", "verified", "verified"])
    text = build_post_text(report)
    assert _count_graphemes(text) <= MAX_GRAPHEMES


def test_post_text_includes_disclaimer():
    report = make_report(["fabricated_doi"])
    text = build_post_text(report)
    assert "Automated check" in text or "automated" in text.lower()


def test_should_post_threshold():
    report_flagged = make_report(["fabricated_doi", "fabricated_doi"])
    report_clean = make_report(extra_statuses=["metadata_error", "metadata_error"])
    assert should_post(report_flagged, threshold=1) is True
    assert should_post(report_clean, threshold=1) is False


def test_metadata_error_never_posts():
    report = make_report(extra_statuses=["metadata_error", "metadata_error"])
    assert report.flagged_count == 0
    assert not should_post(report, threshold=1)


def test_dry_run_does_not_post(capsys):
    from citeagle.bluesky import post_to_bluesky
    post_to_bluesky("test post text", dry_run=True)
    captured = capsys.readouterr()
    assert "dry run" in captured.out.lower()
    assert "NOT sent" in captured.out or "not sent" in captured.out.lower()


def test_post_text_factual_counts():
    report = make_report(["fabricated_doi", "doi_mismatch", "unverified"], ["verified"])
    text = build_post_text(report)
    assert "3 of 4" in text
