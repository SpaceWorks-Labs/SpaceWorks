"""MOD-2: supervised-session use routes (start/end/remove) over HTTP, with conditions."""

from datetime import timedelta

import pytest
from django.utils import timezone
from rest_framework.test import APIClient

from apps.audit.models import AuditLog
from apps.machines.models import SupervisedUse
from apps.presence.models import PresenceSession
from tests.machines.certification_helpers import _member
from tests.machines.test_induction_supervised_l3a import _world

pytestmark = pytest.mark.django_db

API = "/api/v1/member"


def _client(user):
    client = APIClient()
    client.force_authenticate(user)
    return client


def _open(w, *students):
    """An open session led by the machine manager; every student is checked in, so is in the picker's pool."""
    now = timezone.now()
    for student in students:
        PresenceSession.objects.create(account=student, member=student, makerspace=w.space, status="visiting",
                                       started_at=now, expires_at=now + timedelta(hours=2))
    body = {}
    boss = _client(w.manager)
    opened = boss.post(f"{API}/machines/{w.machine.pk}/supervised-sessions", body, format="json")
    assert opened.status_code == 201, opened.content
    sid = opened.json()["id"]
    for student in students:
        added = boss.post(f"{API}/supervised-sessions/{sid}/supervisees", {"user_id": student.pk}, format="json")
        assert added.status_code == 200, added.content
    return boss, sid


def test_use_start_end_round_trip_audits_once_and_refuses_a_double_start_and_double_end():
    w = _world("mod2-use")
    student, _ = _member(w.space, "mod2-student")
    boss, sid = _open(w, student)
    started = boss.post(f"{API}/supervised-sessions/{sid}/uses", {"user_id": student.pk, "note": "First cut"},
                        format="json")
    assert started.status_code == 201 and started.json()["ended_at"] is None
    use_id = started.json()["id"]
    again = boss.post(f"{API}/supervised-sessions/{sid}/uses", {"user_id": student.pk}, format="json")
    assert again.status_code == 409 or again.status_code == 400
    assert again.json().get("code") == "use_already_open"
    assert SupervisedUse.objects.filter(session_id=sid).count() == 1
    ended = boss.post(f"{API}/supervised-uses/{use_id}/end", {}, format="json")
    assert ended.status_code == 200 and ended.json()["ended_at"]
    twice = boss.post(f"{API}/supervised-uses/{use_id}/end", {}, format="json")
    assert twice.json().get("code") == "use_closed" and twice.status_code >= 400
    for action in ("supervised_use_started", "supervised_use_ended"):
        assert AuditLog.objects.filter(action=f"machine_session.{action}", target_id=str(use_id)).count() == 1


def test_use_start_boundaries_note_is_capped_and_unknown_user_is_refused():
    w = _world("mod2-use-bounds")
    student, _ = _member(w.space, "mod2-bounds")
    boss, sid = _open(w, student)
    assert boss.post(f"{API}/supervised-sessions/{sid}/uses", {"user_id": 0}, format="json").status_code == 404  # unknown id: never a 500
    assert boss.post(f"{API}/supervised-sessions/{sid}/uses", {}, format="json").status_code == 400
    assert boss.post(f"{API}/supervised-sessions/{sid}/uses", {"user_id": 99999999}, format="json").status_code == 404
    long_note = "ملاحظة 🔧 " + "n" * 400
    response = boss.post(f"{API}/supervised-sessions/{sid}/uses", {"user_id": student.pk, "note": long_note},
                         format="json")
    assert response.status_code in (201, 400)
    if response.status_code == 201:
        assert len(SupervisedUse.objects.get(session_id=sid).note) <= 300


def test_a_person_not_added_cannot_start_a_use():
    w = _world("mod2-use-notadded")
    student, _ = _member(w.space, "mod2-added")
    stranger, _ = _member(w.space, "mod2-stranger")
    boss, sid = _open(w, student)
    refused = boss.post(f"{API}/supervised-sessions/{sid}/uses", {"user_id": stranger.pk}, format="json")
    assert refused.status_code in (403, 404)
    assert not SupervisedUse.objects.filter(session_id=sid).exists()


def test_other_members_and_other_tenants_cannot_drive_the_session_and_do_not_learn_it_exists():
    w = _world("mod2-use-roles")
    other = _world("mod2-use-roles-other")
    student, _ = _member(w.space, "mod2-r-student")
    boss, sid = _open(w, student)
    use_id = boss.post(f"{API}/supervised-sessions/{sid}/uses", {"user_id": student.pk}, format="json").json()["id"]
    bystander, _ = _member(w.space, "mod2-bystander")
    for user in (bystander, student, other.manager):
        client = _client(user)
        assert client.post(f"{API}/supervised-sessions/{sid}/uses", {"user_id": student.pk},
                           format="json").status_code == 404
        assert client.post(f"{API}/supervised-uses/{use_id}/end", {}, format="json").status_code == 404
        assert client.delete(f"{API}/supervised-sessions/{sid}/supervisees/{student.pk}").status_code == 404
    assert APIClient().post(f"{API}/supervised-uses/{use_id}/end", {}, format="json").status_code in (401, 403)
    assert SupervisedUse.objects.get(pk=use_id).ended_at is None


def test_removing_a_supervisee_ends_their_open_use_and_audits():
    w = _world("mod2-use-remove")
    student, _ = _member(w.space, "mod2-rm-student")
    boss, sid = _open(w, student)
    use_id = boss.post(f"{API}/supervised-sessions/{sid}/uses", {"user_id": student.pk}, format="json").json()["id"]
    removed = boss.delete(f"{API}/supervised-sessions/{sid}/supervisees/{student.pk}")
    assert removed.status_code == 200
    assert SupervisedUse.objects.get(pk=use_id).ended_at is not None
    assert boss.delete(f"{API}/supervised-sessions/{sid}/supervisees/{student.pk}").status_code in (400, 404)


def test_closed_session_refuses_further_uses_and_close_is_not_repeatable():
    w = _world("mod2-use-closed")
    student, _ = _member(w.space, "mod2-cl-student")
    boss, sid = _open(w, student)
    assert boss.post(f"{API}/supervised-sessions/{sid}/close", {}, format="json").status_code == 200
    refused = boss.post(f"{API}/supervised-sessions/{sid}/uses", {"user_id": student.pk}, format="json")
    assert refused.status_code >= 400 and refused.json().get("code") == "supervised_session_closed"
    again = boss.post(f"{API}/supervised-sessions/{sid}/close", {}, format="json")
    assert again.status_code >= 400
    assert AuditLog.objects.filter(action="machine_session.supervised_closed", target_id=str(sid)).count() == 1


def test_capability_off_answers_404_for_use_routes_and_on_again_restores_with_rows_kept():
    w = _world("mod2-use-switch")
    student, _ = _member(w.space, "mod2-sw-student")
    boss, sid = _open(w, student)
    use_id = boss.post(f"{API}/supervised-sessions/{sid}/uses", {"user_id": student.pk}, format="json").json()["id"]
    original = list(w.space.enabled_features)
    w.space.enabled_features = [k for k in original if k != "machines.supervised_sessions"]
    w.space.save(update_fields=["enabled_features"])
    assert boss.post(f"{API}/supervised-uses/{use_id}/end", {}, format="json").status_code == 404
    assert boss.post(f"{API}/supervised-sessions/{sid}/uses", {"user_id": student.pk}, format="json").status_code == 404
    assert SupervisedUse.objects.filter(pk=use_id).exists()
    w.space.enabled_features = original
    w.space.save(update_fields=["enabled_features"])
    assert boss.post(f"{API}/supervised-uses/{use_id}/end", {}, format="json").status_code == 200
