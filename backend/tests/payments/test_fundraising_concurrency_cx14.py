"""A committed OFF wins over a fundraising writer that read the old switch."""

from threading import Event, Thread
from time import monotonic, sleep

import pytest
from django.db import close_old_connections, connection, connections, transaction

from apps.audit.models import AuditLog
from apps.makerspaces.guards import SurfaceOff
from apps.makerspaces.models import Makerspace
from apps.payments.donations.gates import donation_write
from apps.payments.donations.models import DonationCampaign
from tests.l18_local.helpers import setup
from tests.modules.switch_matrix_object_helpers import _no_write

pytestmark = pytest.mark.django_db(transaction=True)


def test_disable_serializes_with_fundraising_write_and_refuses_before_mutation():
    assert connection.vendor == "postgresql"
    space, _manager, _donor = setup("cx14-concurrent")
    started, finished = Event(), Event()
    result, errors, pids = [], [], []
    before = AuditLog.objects.filter(makerspace=space).count()

    def write():
        close_old_connections()
        db = connections["default"]
        try:
            with db.cursor() as cursor:
                cursor.execute("SET lock_timeout = '8s'")
                cursor.execute("SELECT pg_backend_pid()")
                pids.append(cursor.fetchone()[0])
            started.set()
            try:
                with db.execute_wrapper(_no_write), donation_write(space.pk):
                    DonationCampaign.objects.create(makerspace=space, name="Forbidden", slug="forbidden", currency="inr")
            except SurfaceOff as refused:
                result.append((refused.status_code, str(refused.detail["code"])))
        except BaseException as exc:
            errors.append(exc)
        finally:
            db.close()
            finished.set()

    thread = Thread(target=write, daemon=True)
    try:
        with transaction.atomic():
            locked = Makerspace.objects.select_for_update().get(pk=space.pk)
            locked.enabled_features = []
            locked.save(update_fields=["enabled_features"])
            thread.start()
            assert started.wait(5)
            blockers = []
            deadline = monotonic() + 3
            while monotonic() < deadline:
                with connection.cursor() as cursor:
                    cursor.execute("SELECT pg_blocking_pids(%s)", [pids[0]])
                    blockers = cursor.fetchone()[0]
                if blockers:
                    break
                sleep(0.01)
            assert blockers, "Fundraising writer did not wait for the switch transaction"
            assert not finished.is_set()
        thread.join(timeout=10)
    finally:
        if thread.ident is not None:
            thread.join(timeout=10)
    assert not thread.is_alive()
    assert errors == []
    assert result == [(404, "feature_disabled")]
    assert not DonationCampaign.objects.filter(makerspace=space).exists()
    assert AuditLog.objects.filter(makerspace=space).count() == before
