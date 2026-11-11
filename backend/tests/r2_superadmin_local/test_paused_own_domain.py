"""#185(1): a paused space on its own domain or tenant token answers a typed 404 the SPA can show as paused."""
import pytest
from django.utils import timezone
from rest_framework.test import APIClient

from apps.makerspaces.models import Makerspace

from .helpers import REASON, control, manager, space, superadmin

pytestmark = pytest.mark.django_db


def test_bootstrap_of_a_paused_space_says_paused_and_an_unknown_one_does_not(django_capture_on_commit_callbacks):
    lab = space()
    manager(lab)
    with django_capture_on_commit_callbacks(execute=True):
        assert control(superadmin(), lab, "suspend", {"reason": REASON}).status_code == 200
    lab.refresh_from_db()
    paused = APIClient().get("/api/v1/bootstrap", {"tenant": lab.public_code})
    assert paused.status_code == 404 and paused.json()["code"] == "space_paused"
    assert REASON not in str(paused.json())
    unknown = APIClient().get("/api/v1/bootstrap", {"tenant": "NOPE0000"})
    assert unknown.status_code == 404 and "code" not in unknown.json()


def test_archived_paused_space_is_not_discoverable_from_public_status():
    lab = space()
    # Defensive legacy row: archival always takes precedence in public probes.
    Makerspace.objects.filter(pk=lab.pk).update(
        lifecycle_state=Makerspace.LifecycleState.SUSPENDED,
        archived_at=timezone.now(),
    )
    client = APIClient()
    bootstrap = client.get("/api/v1/bootstrap", {"tenant": lab.public_code})
    availability = client.get(f"/api/v1/public/makerspaces/{lab.slug}/availability")
    assert bootstrap.status_code == 404 and "code" not in bootstrap.json()
    assert availability.status_code == 404
