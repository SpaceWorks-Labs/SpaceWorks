"""ID-11: wallet credentials open with membership.wallet_passes OR events.wallet_passes."""
import pytest
from django.urls import reverse

from tests.makerspaces.l4_helpers import space_with_manager
from tests.return_helpers import authenticated_client

pytestmark = pytest.mark.django_db


def _set(space, modules, features):
    space.refresh_from_db()
    space.enabled_modules = sorted(modules)
    space.enabled_features = sorted(features)
    space.save(update_fields=["enabled_modules", "enabled_features"])


def _get(slug, modules, features):
    space, manager = space_with_manager(slug)
    _set(space, modules, features)
    return authenticated_client(manager).get(reverse("admin-wallet-credentials", args=[space.pk]))


def test_membership_switch_alone_opens_the_page():
    assert _get("wc-mem", {"membership"}, {"membership.wallet_passes"}).status_code == 200


def test_events_switch_alone_opens_the_page():
    assert _get("wc-ev", {"events"}, {"events.id_cards", "events.wallet_passes"}).status_code == 200


def test_neither_switch_is_404():
    assert _get("wc-none", {"membership", "events"}, set()).status_code == 404
