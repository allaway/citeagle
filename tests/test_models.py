from citeagle.models import Reference, Verdict, PreprintReport


def test_reference_defaults():
    ref = Reference(raw="test")
    assert ref.authors == []
    assert ref.doi is None


def test_preprintreport_counts():
    from citeagle.models import Reference, Verdict
    ref = Reference(raw="test")
    v1 = Verdict(reference=ref, status="verified", notes="ok")
    v2 = Verdict(reference=ref, status="fabricated_doi", notes="bad")
    report = PreprintReport(preprint_id="test", preprint_title=None, preprint_url=None, verdicts=[v1, v2])
    assert report.counts == {"verified": 1, "fabricated_doi": 1}
    assert report.flagged_count == 1
    assert report.total_count == 2
