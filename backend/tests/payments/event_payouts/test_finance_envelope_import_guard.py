"""encryption/0011: the finance key-row waiver applies only inside the tenant's own import fence."""
import json
from uuid import uuid4

import pytest
from django.db import DatabaseError, connection, transaction
from django.utils import timezone

from apps.payments.event_payouts.payee_models import EventPayeeRevision
from apps.makerspaces.models import Makerspace

pytestmark = pytest.mark.django_db(transaction=True)

MISSING_KEY = "pii:gcm:v1:97:bm9uY2U:Y2lwaGVydGV4dA"


class _Rollback(Exception):
    pass


def _template(bundle):
    from apps.encryption.preparation import prepare_tenants
    with prepare_tenants((bundle.space.pk,)):
        payee = EventPayeeRevision.objects.create(obligation=bundle.obligation, owner=bundle.owner, country="IN",
            template_key="cash", template_version=1, method="cash", details=json.dumps({"holder_name": "Owner"}),
            submitted_at=timezone.now(), disclosure_version=1)
    with connection.cursor() as cursor:
        cursor.execute("SELECT * FROM payments_eventpayeerevision WHERE id=%s", [payee.pk])
        names = [column.name for column in cursor.description]
        return dict(zip(names, cursor.fetchone()))


def _insert(row, details):
    values = {**row, "id": uuid4(), "details": details, "state": "superseded"}
    columns = ", ".join(values)
    placeholders = ", ".join(["%s"] * len(values))
    with connection.cursor() as cursor:
        cursor.execute(f"INSERT INTO payments_eventpayeerevision ({columns}) VALUES ({placeholders})", list(values.values()))


def _close_fence(makerspace_id, operation):
    with connection.cursor() as cursor:
        cursor.execute(
            "UPDATE encryption_piimakerspacewritefence SET state='closed', operation_id=%s, "
            "operation_kind='tenant_import', closed_at=CURRENT_TIMESTAMP, opened_at=NULL WHERE makerspace_id=%s",
            [operation, makerspace_id])
        assert cursor.rowcount == 1
        cursor.execute("SET LOCAL app.pii_fence_operation = %s", [str(operation)])


def _attempt(row, details, *, fence_for=None):
    """Run one insert in a rolled-back transaction; return the database error text or None."""
    try:
        with transaction.atomic():
            if fence_for is not None:
                _close_fence(fence_for, uuid4())
            try:
                _insert(row, details)
            except DatabaseError as exc:
                return str(exc).splitlines()[0]
            raise _Rollback
    except _Rollback:
        return None


def test_outside_an_import_a_payee_row_still_needs_its_key_row(finance_bundle):
    row = _template(finance_bundle)
    assert _attempt(row, MISSING_KEY) == "mandatory finance key unavailable"


def test_inside_another_tenants_import_fence_the_key_row_is_still_required(finance_bundle):
    row = _template(finance_bundle)
    other = Makerspace.objects.create(name="Other tenant", slug="other-import-tenant")
    assert _attempt(row, MISSING_KEY, fence_for=other.pk) == "mandatory finance key unavailable"


def test_inside_the_tenants_own_import_fence_only_the_key_lookup_is_waived(finance_bundle):
    row = _template(finance_bundle)
    space = finance_bundle.space.pk
    assert _attempt(row, MISSING_KEY, fence_for=space) is None
    for bad in ("plaintext bank details", "pii:gcm:v1:0:bad:value", "pii:gcm:v1:3:only-two-parts", ""):
        assert _attempt(row, bad, fence_for=space) == "mandatory finance envelope required", bad
