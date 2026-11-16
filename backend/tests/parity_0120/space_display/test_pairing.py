"""Decision 307c: register, claim, configure, unpair; token scoping; switch off = 404; audit rows."""
import pytest

from apps.audit.models import AuditLog
from apps.makerspaces.models import Makerspace
from apps.presence import display_pairing
from apps.presence.models_display import DisplayScreen

pytestmark = pytest.mark.django_db
REGISTER = "/api/v1/space-displays/register/"


def _state(lane, token):
    return lane.client().get(f"/api/v1/space-displays/{token}/state/")


def _admin(space):
    return f"/api/v1/admin/makerspace/{space.pk}/presence-displays"


def _register(lane):
    body = lane.client().post(REGISTER).json()
    return body["token"], body["code"]


def test_register_then_claim_then_poll(lane):
    token, code = _register(lane)
    assert _state(lane, token).json()["state"] == "unclaimed"
    admin = lane.client(lane.staff)
    claimed = admin.post(_admin(lane.space), {"code": code.lower(), "name": "Lobby", "panels": ["here_now", "calendar"],
                                               "rotation_seconds": 20}, format="json")
    assert claimed.status_code == 201 and claimed.json()["rotation_seconds"] == 20
    state = _state(lane, token).json()
    assert state["state"] == "paired" and state["config"]["panels"] == ["here_now", "calendar"]
    assert state["machines"] is None and state["space"]["slug"] == "display-lane"
    assert AuditLog.objects.filter(action="presence.display_claimed", makerspace=lane.space).count() == 1
    assert admin.post(_admin(lane.space), {"code": code}, format="json").status_code == 404  # code is single use


def test_secret_is_stored_only_as_a_digest(lane):
    token, _ = _register(lane)
    row = DisplayScreen.objects.get()
    assert row.token_digest == display_pairing.digest(token) and token not in row.token_digest


def test_config_change_is_live_and_audited(lane):
    token, code = _register(lane)
    admin = lane.client(lane.staff)
    row_id = admin.post(_admin(lane.space), {"code": code}, format="json").json()["id"]
    before = _state(lane, token).json()["config"]["version"]
    done = admin.patch(f"{_admin(lane.space)}/{row_id}", {"rotation_seconds": 45, "announcement": "Open day"}, format="json")
    assert done.status_code == 200
    after = _state(lane, token).json()
    assert after["config"]["version"] == before + 1 and after["config"]["rotation_seconds"] == 45
    assert after["announcement"] is None  # the announcement panel is not selected
    assert admin.patch(f"{_admin(lane.space)}/{row_id}", {"rotation_seconds": 3}, format="json").status_code == 400
    assert AuditLog.objects.filter(action="presence.display_updated").count() == 1


def test_unpair_revokes_the_secret(lane):
    token, code = _register(lane)
    admin = lane.client(lane.staff)
    row_id = admin.post(_admin(lane.space), {"code": code}, format="json").json()["id"]
    assert admin.delete(f"{_admin(lane.space)}/{row_id}").status_code == 204
    assert _state(lane, token).status_code == 404
    assert AuditLog.objects.filter(action="presence.display_unpaired").count() == 1
    assert admin.get(_admin(lane.space)).json()["displays"] == []


def test_token_is_scoped_to_its_space_and_unknown_token_is_404(lane):
    assert _state(lane, "not-a-real-token").status_code == 404
    token, code = _register(lane)
    lane.client(lane.staff).post(_admin(lane.space), {"code": code}, format="json")
    elsewhere = Makerspace.objects.create(name="Elsewhere", slug="display-elsewhere")
    other = lane.person("other-manager", manager=True, target=elsewhere)
    # another space's manager can neither list nor unpair this space's screen
    row_id = DisplayScreen.objects.get().pk
    assert lane.client(other).delete(f"{_admin(lane.space)}/{row_id}").status_code in (403, 404)
    assert DisplayScreen.objects.get().revoked_at is None


def test_switch_off_is_404_everywhere(lane):
    token, code = _register(lane)
    admin = lane.client(lane.staff)
    admin.post(_admin(lane.space), {"code": code}, format="json")
    lane.space.enabled_features = [f for f in lane.space.enabled_features if f != "presence.public_display"]
    lane.space.save(update_fields=["enabled_features"])
    assert _state(lane, token).status_code == 404
    _, second = _register(lane)
    assert admin.post(_admin(lane.space), {"code": second}, format="json").status_code == 404


def test_members_without_manage_makerspace_cannot_claim(lane):
    _, code = _register(lane)
    member = lane.person("plain")
    assert lane.client(member).post(_admin(lane.space), {"code": code}, format="json").status_code in (403, 404)
    assert lane.client().post(_admin(lane.space), {"code": code}, format="json").status_code == 401


def test_limit_key_refuses_the_next_claim(lane):
    lane.space.resource_limit_overrides = {"paired_displays": 1}
    lane.space.save(update_fields=["resource_limit_overrides"])
    admin = lane.client(lane.staff)
    _, first = _register(lane)
    _, second = _register(lane)
    assert admin.post(_admin(lane.space), {"code": first}, format="json").status_code == 201
    refused = admin.post(_admin(lane.space), {"code": second}, format="json")
    assert refused.status_code == 409 and refused.json()["code"] == "paired_displays_quota_reached"


def test_unclaimed_code_expires(lane):
    from datetime import timedelta
    from django.utils import timezone
    token, _ = _register(lane)
    DisplayScreen.objects.update(code_expires_at=timezone.now() - timedelta(minutes=1))
    assert _state(lane, token).status_code == 404
