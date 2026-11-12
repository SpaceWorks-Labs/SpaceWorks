"""CARD-STUDIO-2 (decision 344) fixtures: the card_engine helpers plus a platform test host."""
import pytest

from tests.parity_0120.card_engine.conftest import document, layer, png, silhouette, uid  # noqa: F401 (re-exported)


@pytest.fixture(autouse=True)
def card_test_host(settings):
    settings.INFRA_HOSTS = {*settings.INFRA_HOSTS, "testserver"}
