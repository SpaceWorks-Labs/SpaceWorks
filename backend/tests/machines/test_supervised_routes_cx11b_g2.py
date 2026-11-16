"""Every supervised route, with real participant/use/session effects and 520 object standing."""
from datetime import timedelta

import pytest
from django.utils import timezone

from apps.machines.models import SupervisedParticipant, SupervisedSession, SupervisedUse
from apps.presence.models import PresenceSession
from tests.machines.route_support_cx11b_g2 import command, prove, rows, world
from tests.rbac_f6_helpers import community_member

pytestmark = [pytest.mark.django_db, pytest.mark.area_machines]
ROUTES = [("member-supervised-session-open", "post"), ("member-supervised-sessions", "get"),
          ("member-supervised-session", "get"), ("member-supervised-supervisees", "post"),
          ("member-supervised-people", "get"), ("member-supervised-supervisee-remove", "delete"),
          ("member-supervised-use-start", "post"), ("member-supervised-use-end", "post"),
          ("member-supervised-session-close", "post")]


@pytest.mark.parametrize("native", [False, True], ids=["browser", "native"])
@pytest.mark.parametrize("key", ["machines", "machines.supervised_sessions"])
@pytest.mark.parametrize("name,method", ROUTES)
def test_supervised_operation_has_exact_effect_and_retains_its_rows(native, key, name, method):
    w = world(native)
    student = community_member(w.space, "g2-student").user
    student.display_name = "G2 Student"
    student.save(update_fields=["display_name"])
    now = timezone.now()
    PresenceSession.objects.create(makerspace=w.space, account=student, member=student, status="visiting",
                                   started_at=now, expires_at=now + timedelta(hours=2))
    opening = name.endswith("session-open")
    listing = name == "member-supervised-sessions"
    session = None if opening else SupervisedSession.objects.create(makerspace=w.space, machine=w.machine,
        instructor=w.actor, opened_at=now - timedelta(minutes=10), note="Retained workshop")
    add = name == "member-supervised-supervisees"
    picker = name == "member-supervised-people"
    participant = None
    use = None
    if session and not add and not picker:
        participant = SupervisedParticipant.objects.create(session=session, user=student, added_by=w.actor,
                                                           added_at=now - timedelta(minutes=5))
    if name in {"member-supervised-use-end", "member-supervised-supervisee-remove", "member-supervised-session-close"}:
        use = SupervisedUse.objects.create(session=session, user=student, instructor=w.actor,
                                           started_at=now - timedelta(minutes=2), note="Retained cut")
    args = [w.machine.pk] if opening else [w.space.pk] if listing else [use.pk] if name.endswith("use-end") else [session.pk]
    if name.endswith("supervisee-remove"):
        args.append(student.pk)
    body = {"note": "Restored workshop"} if opening else {"q": "G2 Student"} if picker else (
        {"user_id": student.pk, **({"note": "Restored cut"} if name.endswith("use-start") else {})} if add or
        name.endswith("use-start") else {})
    event = {"member-supervised-session-open": "supervised_opened", "member-supervised-supervisees": "supervisee_added",
             "member-supervised-supervisee-remove": "supervisee_removed", "member-supervised-use-start": "supervised_use_started",
             "member-supervised-use-end": "supervised_use_ended", "member-supervised-session-close": "supervised_closed"}.get(name)

    def check(response):
        if opening:
            saved = SupervisedSession.objects.get(pk=response.data["id"])
            assert (saved.machine_id, saved.instructor_id, saved.note, saved.closed_at) == (
                w.machine.pk, w.actor.pk, "Restored workshop", None)
            assert SupervisedSession.objects.filter(machine=w.machine).count() == 1
        elif listing:
            assert [(r["id"], r["note"], r["machine"]) for r in rows(response)] == [(session.pk, "Retained workshop", w.machine.pk)]
        elif picker:
            assert response.data == {"results": [{"id": student.pk, "display_name": "G2 Student"}]}
        elif add:
            saved = SupervisedParticipant.objects.get(session=session, user=student)
            assert (saved.added_by_id, saved.removed_at) == (w.actor.pk, None)
            assert [r["user"] for r in response.data["participants"]] == [student.pk]
        elif name.endswith("supervisee-remove"):
            assert SupervisedParticipant.objects.get(pk=participant.pk).removed_at is not None
            assert SupervisedUse.objects.get(pk=use.pk).ended_at is not None
        elif name.endswith("use-start"):
            saved = SupervisedUse.objects.get(pk=response.data["id"])
            assert (saved.user_id, saved.session_id, saved.note, saved.ended_at) == (student.pk, session.pk, "Restored cut", None)
        elif name.endswith("use-end"):
            assert SupervisedUse.objects.get(pk=use.pk).ended_at is not None
            assert response.data["id"] == use.pk
            assert response.data["ended_at"] is not None
        elif name.endswith("session-close"):
            saved = SupervisedSession.objects.get(pk=session.pk)
            assert saved.closed_at is not None
            assert saved.closed_by_id == w.actor.pk
            assert SupervisedUse.objects.get(pk=use.pk).ended_at is not None
        else:
            assert (response.data["id"], response.data["machine"], response.data["note"]) == (
                session.pk, w.machine.pk, "Retained workshop")
            assert [r["user"] for r in response.data["participants"]] == [student.pk]

    # 520 conceals addressed objects. Open/list are person discovery surfaces:
    # open refuses absent instructor authority (403); list returns only led/managed rows.
    # Their feature refusal is public to those person callers (494/486).
    off = (404, "module_disabled" if key == "machines" else "feature_disabled")
    foreign = (403, "permission_denied") if native or opening else (200, None) if listing else (404, "not_found")
    prove(w, key, lambda c: command(c, name, method, args, body), check,
          status=201 if opening or name.endswith("use-start") else 200,
          audits=(f"machine_session.{event}",) if event else (), off=off,
          foreign=foreign,
          foreign_check=(lambda r: _empty(r)) if listing else None,
          foreign_off=foreign if native else off if opening or listing else None)


def _empty(response):
    assert response.data["count"] == 0
    assert response.data["results"] == []
