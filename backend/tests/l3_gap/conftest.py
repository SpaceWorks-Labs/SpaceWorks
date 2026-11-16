"""L3 HTTP fixtures use Django's test host as a recognised platform host (as tests/events do)."""

import pytest


@pytest.fixture(autouse=True)
def card_test_host(settings):
    settings.INFRA_HOSTS = {*settings.INFRA_HOSTS, "testserver"}
