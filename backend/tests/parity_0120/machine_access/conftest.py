"""Decision 319 suites run with the REAL default: a new machine needs a grant."""
import pytest


@pytest.fixture(autouse=True)
def open_new_machines():
    yield
