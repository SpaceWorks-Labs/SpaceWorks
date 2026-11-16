"""Event HTTP fixtures use Django's test host as a recognized platform host."""

import pytest


@pytest.fixture(autouse=True)
def event_test_host(settings):
    settings.INFRA_HOSTS = {*settings.INFRA_HOSTS, "testserver"}
