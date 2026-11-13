"""Portability cannot revive accounts, and a late fee remains in the core ledger."""

from datetime import timedelta
from decimal import Decimal

import pytest
from django.utils import timezone

from apps.accounts.models import User
from apps.audit.models import AuditLog
from apps.hardware_requests.loan_payments import on_request_closed
from apps.hardware_requests.models import HardwareRequest
from apps.payments.models import Payment
from apps.tenant_migration.identity_resolution import _create_walk_in
from tests.accounts.test_support_m1d import account, due, m1d_config
from tests.hardware_requests.test_loan_payments import loan_space

pytestmark = pytest.mark.django_db


@pytest.mark.parametrize("purged", [False, True])
def test_import_never_reactivates_a_deleted_source_or_copies_purged_identity(purged):
    now = timezone.now()
    source = {"username": "private-source", "first_name": "Private", "last_name": "Person",
        "display_name": "Private Person", "phone": "private-phone", "email": "private@example.test",
        "is_active": True, "is_staff": True, "is_superuser": True, "role": "superadmin",
        "date_joined": (now - timedelta(days=200)).isoformat(),
        "deletion_requested_at": (now - timedelta(days=91)).isoformat(),
        "deletion_purge_after": (now - timedelta(days=1)).isoformat(),
        "account_purged_at": now.isoformat() if purged else ""}
    row = _create_walk_in(source, 987654)
    row.refresh_from_db()
    assert not row.is_active and not row.has_usable_password()
    assert not row.is_staff and not row.is_superuser and row.role == User.Role.REQUESTER
    assert row.deletion_requested_at == now - timedelta(days=91)
    assert row.deletion_purge_after == now - timedelta(days=1)
    assert row.account_purged_at == (now if purged else None)
    assert row.email == row.phone_e164 == ""
    if purged:
        assert row.username.startswith("walkin_deleted_") and row.display_name == "Deleted member"
        assert "private" not in row.username and "source" not in row.username
        assert row.first_name == row.last_name == row.phone == ""
    else:
        assert row.first_name == "Private" and row.last_name == "Person"


def test_late_fee_after_deletion_still_records_and_audits_exactly_one_debt():
    tenant, actor = loan_space("m1d-late-fee", loan_late_fee_per_day=Decimal("3.00"))
    user = due(account())
    now = timezone.now()
    row = HardwareRequest.objects.create(makerspace=tenant, requester=user, requester_username=user.username,
        status="returned", closed_at=now, return_due_at=now - timedelta(days=2))
    charge = on_request_closed(row.pk, actor, now)
    assert charge.member_id == user.pk and charge.amount == Decimal("6.00") and charge.status == "pending"
    assert on_request_closed(row.pk, actor, now).pk == charge.pk
    assert Payment.objects.filter(member=user).count() == 1
    entry = AuditLog.objects.get(action="account.obligation_after_deletion", target_id=str(user.pk))
    assert entry.makerspace_id == tenant.pk and entry.meta["payment_id"] == charge.pk
