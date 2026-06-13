import pytest


@pytest.fixture
def sample_verified_ref():
    from citeagle.models import Reference
    return Reference(
        raw="Smith J, Doe A (2020). A great paper on biology. Nature, 123, 456.",
        authors=["Smith", "Doe"],
        title="A great paper on biology",
        year=2020,
        venue="Nature",
        doi="10.1234/nature.2020.001",
    )


@pytest.fixture
def sample_no_doi_ref():
    from citeagle.models import Reference
    return Reference(
        raw="Jones B, Brown C (2019). Methods in computational biology. Cell, 99, 12.",
        authors=["Jones", "Brown"],
        title="Methods in computational biology",
        year=2019,
        venue="Cell",
        doi=None,
    )
