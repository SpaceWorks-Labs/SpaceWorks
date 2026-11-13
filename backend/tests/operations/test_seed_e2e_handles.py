"""The e2e seed must leave every personal account with a username handle (decision 308).

Without one, every state-changing staff or member request answers 403 `handle_required`, so the
whole Playwright suite fails before it tests anything."""
import json

import pytest
from django.core.management import call_command

from apps.accounts.models import User
from apps.makerspaces.public_profile_handles import has_handle


@pytest.mark.django_db
def test_seeded_accounts_have_a_handle(settings, tmp_path):
    settings.DEBUG = True
    settings.EVENT_STATION_PIN_PEPPER = "p" * 40  # the seeded kiosk station derives its PIN digest from it
    seed = tmp_path / "seed.json"
    call_command("seed_e2e", "--write-json", str(seed), verbosity=0)
    seeded = json.loads(seed.read_text())
    for role in ("manager", "member"):
        user = User.objects.get(username=seeded[role]["username"])
        assert has_handle(user), f"{role} would be blocked with handle_required"
