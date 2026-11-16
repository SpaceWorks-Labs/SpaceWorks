"""O-B6 fixtures: Django's test host counts as a platform host; the hosting-request fixtures are reused."""
import pytest

from tests.hosting_requests.conftest import managed, self_host  # noqa: F401


@pytest.fixture(autouse=True)
def card_test_host(settings):
    settings.INFRA_HOSTS = {*settings.INFRA_HOSTS, "testserver"}
