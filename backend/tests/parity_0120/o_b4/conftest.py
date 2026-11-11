"""O-B4 HTTP fixtures: Django's test host counts as a platform host, like the L3 card tests."""
import pytest


@pytest.fixture(autouse=True)
def card_test_host(settings):
    settings.INFRA_HOSTS = {*settings.INFRA_HOSTS, "testserver"}
