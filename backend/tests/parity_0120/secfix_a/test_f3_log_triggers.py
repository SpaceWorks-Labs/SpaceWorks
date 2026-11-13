"""SECURITY-REVIEW L-A4: adapter event, access and usage logs are append-only at the database (devices 0013).

Attack cases: an ORM ``update()`` or ``delete()`` that skips ``Model.save`` is refused by Postgres. Normal cases: the
schema's own ``ON DELETE SET NULL`` (unbinding a target), an account merge moving the member, and an authorized purge
(``app.allow_immutable_delete``) still work.
"""
import uuid

import pytest
from django.db import DatabaseError, connection, transaction
from django.urls import reverse
from django.utils import timezone

from apps.backup.managed.function_catalog import APPLICATION_FUNCTIONS
from apps.devices.models import AdapterAccessLog, AdapterBinding, AdapterEvent, AdapterUsageLog
from tests.parity_0120.adapter_api.adapter_case import adapter_case, plain_member

pytestmark = pytest.mark.django_db(transaction=True)


def _logs(case, member=None):
    device, space, now = case["device"], case["space"], timezone.now()
    binding = AdapterBinding.objects.get(pk=case["binding_id"])
    return {
        "event": AdapterEvent.objects.create(makerspace=space, device=device, binding=binding, operation_id=uuid.uuid4(),
                                             event_type="machine.state", capability="status", observed_at=now),
        "access": AdapterAccessLog.objects.create(makerspace=space, device=device, binding=binding, member=member,
                                                  credential_type="nfc", allowed=True, reason="ok"),
        "usage": AdapterUsageLog.objects.create(makerspace=space, device=device, binding=binding,
                                                operation_id=uuid.uuid4(), started_at=now, ended_at=now,
                                                outcome="completed"),
    }


def _set(name, value):
    with connection.cursor() as cursor:
        cursor.execute("SELECT set_config(%s, %s, true)", [name, value])


def test_rewriting_or_deleting_a_log_row_is_refused_by_the_database():
    case = adapter_case("f3-trg-refuse")
    rows = _logs(case)
    for model, row, change in ((AdapterEvent, rows["event"], {"event_type": "forged"}),
                               (AdapterAccessLog, rows["access"], {"allowed": False}),
                               (AdapterUsageLog, rows["usage"], {"active_minutes": 999})):
        with pytest.raises(DatabaseError), transaction.atomic():
            model.objects.filter(pk=row.pk).update(**change)
        with pytest.raises(DatabaseError), transaction.atomic():
            model.objects.filter(pk=row.pk).delete()
        # Nulling the binding is allowed only on its own, never smuggled in with another change.
        with pytest.raises(DatabaseError), transaction.atomic():
            model.objects.filter(pk=row.pk).update(binding=None, **change)
        assert model.objects.filter(pk=row.pk).exists()


def test_a_member_cannot_be_reattributed_outside_an_account_merge():
    case = adapter_case("f3-trg-member")
    first, second = plain_member("f3-trg-a", case["space"]), plain_member("f3-trg-b", case["space"])
    row = _logs(case, member=first)["access"]
    with pytest.raises(DatabaseError), transaction.atomic():
        AdapterAccessLog.objects.filter(pk=row.pk).update(member=second)
    # Normal: the account merge (its run id GUC set) moves the member to the survivor.
    with transaction.atomic():
        _set("app.account_unification_run_id", str(uuid.uuid4()))
        AdapterAccessLog.objects.filter(pk=row.pk).update(member=second)
        _set("app.account_unification_run_id", "")
    assert AdapterAccessLog.objects.get(pk=row.pk).member_id == second.pk


def test_unbinding_a_target_still_nulls_the_binding_on_its_logs():
    case = adapter_case("f3-trg-unbind")
    rows = _logs(case)
    response = case["client"].delete(reverse("devices:admin-adapter-binding-detail", args=[case["binding_id"]]))
    assert response.status_code == 204
    for model, row in ((AdapterEvent, rows["event"]), (AdapterAccessLog, rows["access"]),
                       (AdapterUsageLog, rows["usage"])):
        assert model.objects.get(pk=row.pk).binding_id is None


def test_a_deleted_account_still_nulls_the_member():
    case = adapter_case("f3-trg-account")
    gone = plain_member("f3-trg-gone", case["space"])
    row = _logs(case, member=gone)["access"]
    with transaction.atomic():
        AdapterAccessLog.objects.filter(pk=row.pk).update(member=None)  # what ON DELETE SET NULL issues
    assert AdapterAccessLog.objects.get(pk=row.pk).member_id is None


def test_an_authorized_purge_may_delete_the_rows():
    case = adapter_case("f3-trg-purge")
    rows = _logs(case)
    with transaction.atomic():
        _set("app.allow_immutable_delete", "on")
        for model, row in ((AdapterEvent, rows["event"]), (AdapterAccessLog, rows["access"]),
                           (AdapterUsageLog, rows["usage"])):
            model.objects.filter(pk=row.pk).delete()
    assert not AdapterAccessLog.objects.filter(pk=rows["access"].pk).exists()


def test_the_guard_function_is_catalogued_for_backups():
    assert "devices_adapter_log_append_only" in APPLICATION_FUNCTIONS
