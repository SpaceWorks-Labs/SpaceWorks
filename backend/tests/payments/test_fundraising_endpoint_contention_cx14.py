"""R1: OFF wins against real authenticated handlers after their initial lookup."""

from threading import Event, Thread
from time import monotonic, sleep

import pytest
from django.db import close_old_connections, connection, connections, transaction
from django.urls import reverse

from apps.audit.models import AuditLog
from apps.makerspaces.models import Makerspace
from apps.payments.donations import views_sponsor_logo, views_sponsors, views_staff, views_staff_area
from tests.l18_local.helpers import admin
from tests.modules.switch_matrix_object_helpers import no_domain_writes
from tests.payments.test_fundraising_mutations_cx14 import mutation_world, snapshot

pytestmark = pytest.mark.django_db(transaction=True)
CASES = [(kind, key) for kind, keys in (
    ("logo", ("finance.donations", "finance.sponsors")),
    ("confirm", ("finance.donations", "billing.offline_claims")),
    ("reject", ("finance.donations", "billing.offline_claims")),
    ("campaign", ("finance.donations",)),
    ("sponsor", ("finance.donations", "finance.sponsors")),
    ("gift", ("finance.donations",)),
) for key in keys]


@pytest.mark.parametrize("native", [False, True], ids=["browser", "native"])
@pytest.mark.parametrize("kind,key", CASES)
def test_endpoint_waits_for_disable_then_refuses_without_attempting_write(kind, key, native, monkeypatch):
    assert connection.vendor == "postgresql"
    world_kind = kind if kind in {"confirm", "reject"} else "logo"
    space, api, row, _, _, release, method, url = mutation_world(world_kind, native, monkeypatch)
    body = {"note": "Reviewed transfer"}
    if kind == "logo":
        module, lookup = views_sponsor_logo, "_row"
    elif kind in {"confirm", "reject"}:
        module, lookup = views_staff_area, "gift_or_404"
    else:
        module, lookup = (views_sponsors if kind == "sponsor" else views_staff), "staff_space"
        method = "post"
        if kind == "campaign":
            url, body = admin(space, "/campaigns"), {"name": "Forbidden", "slug": "forbidden"}
        elif kind == "sponsor":
            url = reverse("admin-sponsors", kwargs={"makerspace_id": space.pk})
            body = {"name": "Forbidden"}
        else:
            url, body = admin(space), {"donor_name": "Giver", "donor_email": "giver@example.test", "amount": "25",
                "settlement": {"method": "cash", "reference": "CX14", "received_at": "2026-11-14T10:00:00Z"}}
    original = getattr(module, lookup)
    looked_up, resume, finished = Event(), Event(), Event()
    result, errors, pids = [], [], []
    before = snapshot(space)
    audits = list(AuditLog.objects.filter(makerspace=space).order_by("pk").values())

    def pause_after_lookup(*args, **kwargs):
        found = original(*args, **kwargs)  # All real scope, permission and initial feature checks still run.
        with connections["default"].cursor() as cursor:
            cursor.execute("SELECT pg_backend_pid()")
            pids.append(cursor.fetchone()[0])
        looked_up.set()
        assert resume.wait(8), "Disable never reached its locked update"
        return found

    monkeypatch.setattr(module, lookup, pause_after_lookup)

    def request():
        close_old_connections()
        db = connections["default"]
        try:
            with db.cursor() as cursor:
                cursor.execute("SET lock_timeout = '8s'")
            # Authentication activity is allowed, then every attempted domain DML/DDL
            # raises before execution, even if the endpoint would later roll it back.
            with no_domain_writes():
                response = getattr(api, method)(url, body, format="json")
            result.append((response.status_code, response.json().get("code")))
        except BaseException as exc:
            errors.append(exc)
        finally:
            db.close()
            finished.set()

    thread = Thread(target=request, daemon=True)
    thread.start()
    try:
        assert looked_up.wait(6), errors
        with transaction.atomic():
            locked = Makerspace.objects.select_for_update().get(pk=space.pk)
            locked.enabled_features = sorted(set(locked.enabled_features) - {key})
            locked.save(update_fields=["enabled_features"])
            resume.set()
            blockers = []
            deadline = monotonic() + 3
            while monotonic() < deadline and not finished.is_set():
                with connection.cursor() as cursor:
                    cursor.execute("SELECT pg_blocking_pids(%s)", [pids[0]])
                    blockers = cursor.fetchone()[0]
                if blockers:
                    break
                sleep(0.01)
            assert blockers, ("Handler did not wait for the makerspace switch lock", errors, result)
            assert not finished.is_set()
        thread.join(timeout=10)
    finally:
        resume.set()
        thread.join(timeout=10)
    assert not thread.is_alive()
    assert errors == []
    assert result == [(404, "feature_disabled")]
    assert snapshot(space) == before
    assert list(AuditLog.objects.filter(makerspace=space).order_by("pk").values()) == audits
    release.assert_not_called()
