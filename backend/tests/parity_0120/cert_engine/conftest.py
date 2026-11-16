"""Certificate-engine tests: the test host counts as a platform host (the card-template routes are platform-gated)."""
import pytest


@pytest.fixture(autouse=True)
def card_test_host(settings):
    settings.INFRA_HOSTS = {*settings.INFRA_HOSTS, "testserver"}
