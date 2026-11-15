"""Real lookup/disable contention for R4, with attempted SQL writes forbidden."""

from threading import Event, Thread
from time import monotonic, sleep

from django.db import close_old_connections, connection, connections, transaction

from apps.makerspaces.models import Makerspace
from tests.modules.switch_matrix_object_helpers import no_domain_writes
from tests.payments.test_fundraising_public_code_cx14 import code_snapshot


def refuse_after_disable(space, api, url, body, key, expected, monkeypatch, module, lookup):
    assert connection.vendor == "postgresql"
    original = getattr(module, lookup)
    looked_up, resume, finished = Event(), Event(), Event()
    results, errors, pids = [], [], []
    before = code_snapshot(space)
    with connection.cursor() as cursor:
        cursor.execute("SELECT pg_backend_pid()")
        disabler_pid = cursor.fetchone()[0]

    def pause(*args, **kwargs):
        found = original(*args, **kwargs)  # Preserve real scope, authority and initial gates.
        with connections["default"].cursor() as cursor:
            cursor.execute("SELECT pg_backend_pid()")
            pids.append(cursor.fetchone()[0])
        looked_up.set()
        assert resume.wait(8), "Disabler did not reach its locked update"
        return found

    monkeypatch.setattr(module, lookup, pause)

    def request():
        close_old_connections()
        db = connections["default"]
        try:
            with db.cursor() as cursor:
                cursor.execute("SET lock_timeout = '8s'")
            with no_domain_writes():
                response = api.post(url, body, format="json")
            results.append((response.status_code, response.json().get("code")))
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
                if disabler_pid in blockers:
                    break
                sleep(0.01)
            assert disabler_pid in blockers, ("Missing fresh lock contention", errors, results)
            assert not finished.is_set()
        thread.join(timeout=10)
    finally:
        resume.set()
        thread.join(timeout=10)
    assert not thread.is_alive()
    assert errors == []
    assert results == [expected]
    assert code_snapshot(space) == before
    monkeypatch.setattr(module, lookup, original)
