"""Decision 300(b): HUB_LANDING_ENABLED reaches the SPA through the existing public config."""
import pytest
from rest_framework.test import APIClient

CONFIG = "/api/v1/config"


@pytest.mark.django_db
@pytest.mark.parametrize("value", [True, False])
def test_public_config_exposes_landing_enabled(settings, value):
    settings.HUB_LANDING_ENABLED = value
    response = APIClient().get(CONFIG)
    assert response.status_code == 200
    assert response.json()["landing_enabled"] is value


@pytest.mark.django_db
def test_landing_is_on_by_default():
    from django.conf import settings as live_settings

    # The default must hold on every install, self-hosted included.
    assert getattr(live_settings, "HUB_LANDING_ENABLED", True) is True
    assert APIClient().get(CONFIG).json()["landing_enabled"] is True


@pytest.mark.django_db
def test_landing_flag_needs_no_credentials_and_is_not_cached(settings):
    settings.HUB_LANDING_ENABLED = False
    response = APIClient().get(CONFIG)
    assert response.status_code == 200
    assert response["Cache-Control"] == "no-store"
