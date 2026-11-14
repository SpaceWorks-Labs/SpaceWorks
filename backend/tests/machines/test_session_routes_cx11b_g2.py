"""Metered member session route reads and real start/stop, with independent machine/session gates."""
from datetime import timedelta

import pytest
from django.utils import timezone

from apps.machines.models import MachineSession, MachineUsageEntry
from apps.payments.models import Payment
from tests.machines.member_support_cx11b_g2 import member_world
from tests.machines.route_support_cx11b_g2 import command, prove

pytestmark = [pytest.mark.django_db, pytest.mark.area_machines]
ROUTES = [("member-machine-session-preview", "get"), ("member-machine-session-start", "post"),
          ("member-machine-sessions", "get"), ("member-machine-session-stop", "post")]


@pytest.mark.parametrize("native", [False, True], ids=["browser", "native"])
@pytest.mark.parametrize("key", ["machines", "machines.sessions"])
@pytest.mark.parametrize("name,method", ROUTES)
def test_member_session_route_has_real_state_and_owner_effect(native, key, name, method, monkeypatch):
    w = member_world(native)
    now = timezone.now()
    monkeypatch.setattr("apps.machines.sessions_service.timezone.now", lambda: now)
    session = None
    starting = name.endswith("session-start")
    listing = name == "member-machine-sessions"
    stopping = name.endswith("session-stop")
    if listing or stopping:
        session = MachineSession.objects.create(makerspace=w.space, machine=w.machine, machine_type=w.kind,
            member=w.member, source="member_qr", started_at=now - timedelta(minutes=10))
    args = [] if listing else [session.pk] if stopping else [w.machine.pk]
    payments = Payment.objects.count()

    def check(response):
        if starting:
            saved = MachineSession.objects.get(pk=response.data["id"])
            assert (saved.machine_id, saved.member_id, saved.source, saved.ended_at) == (w.machine.pk, w.member.pk, "member_qr", None)
            assert MachineSession.objects.filter(machine=w.machine).count() == 1
        elif stopping:
            saved = MachineSession.objects.get(pk=session.pk)
            assert (saved.stop_reason, saved.stopped_by_id, saved.duration_minutes) == ("member", w.member.pk, 10)
            assert saved.ended_at is not None
            assert response.data["id"] == session.pk
            usage = MachineUsageEntry.objects.get(machine=w.machine, source="session")
            assert (usage.member_id, usage.duration_minutes, usage.started_at) == (w.member.pk, 10, session.started_at)
        elif listing:
            assert [(r["id"], r["machine_id"]) for r in response.data] == [(session.pk, w.machine.pk)]
        else:
            assert (response.data["machine_id"], response.data["machine_name"], response.data["can_start"],
                    response.data["refusal"]) == (w.machine.pk, "Retained machine", True, None)
        assert Payment.objects.count() == payments

    def empty(response):
        assert response.data == []

    def call(c):
        query = {"makerspace": c._credentials.get("HTTP_X_MAKERSPACE_ID", w.space.pk)} if listing else None
        return command(c, name, method, args, query)

    # Person list is empty for others; machine lookup and addressed stop are
    # membership/owner scoped before switch disclosure (520).
    prove(w, key, call, check, status=201 if starting else 200,
          audits=("machine_session.started",) if starting else ("machine_session.stopped",) if stopping else (),
          off=(200, None) if listing else (404, "not_found"), off_check=empty if listing else None,
          foreign=(200, None) if listing else (404, "not_found"), foreign_check=empty if listing else None)
