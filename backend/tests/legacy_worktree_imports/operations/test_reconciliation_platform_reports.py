"""Platform counts preserve provenance, hidden buckets and actual collected revenue."""
from decimal import Decimal
from types import SimpleNamespace

import pytest

from apps.accounts.models import User
from apps.hardware_requests.models import HardwareRequest
from apps.integrations.models_tracking import SmsSendLog
from apps.operations.platform_scope import _platform_context_for_view
from apps.operations.reports_platform_services import build_platform_services
from apps.operations.reports_platform_usage import build_platform_usage
from apps.payments.models import Payment
from tests.operations.reconciliation_report_helpers import delivery, report_space
from tests.return_helpers import make_user

pytestmark = pytest.mark.django_db


def context():
    actor = make_user("recon-r-platform", role=User.Role.SUPERADMIN, access_status="active")
    return _platform_context_for_view(SimpleNamespace(user=actor))


def test_platform_reports_canonical_addressed_counts_and_anonymous_hidden_usage(monkeypatch):
    visible = report_space("recon-r-visible")
    delivery(visible, state="sent")
    SmsSendLog.objects.create(makerspace=visible, provider_source="platform", status="sent")
    # Push migration is P's independent contract; isolate SMS/WA metering here.
    monkeypatch.setattr("apps.operations.reports_platform_services.push_querysets", lambda ids: ())
    rows = build_platform_services(platform_context=context()).records
    sms = [r for r in rows if r["service"] == "sms"]
    assert {r.get("purpose") for r in sms if r.get("makerspace_id") == visible.pk} == {"otp", "notifications"}
    assert sum(r["count"] for r in sms if r.get("makerspace_id") == visible.pk) == 2
    # Decision 110: the hidden-makerspace anonymous bucket is gone (superadmin always on).
    assert not any(r.get("bucket") == "hidden_makerspaces" for r in rows)
    assert "PRIVATE" not in str(rows)


def test_pending_bill_is_debt_and_never_platform_collected_revenue():
    space = report_space("recon-r-revenue")
    user = make_user("recon-r-payer")
    loan = HardwareRequest.objects.create(makerspace=space, requester=user,
        requester_username=user.username, status="issued")
    Payment.objects.create(makerspace=space, member=user, subject_type="loan_deposit", subject_id=loan.pk,
        amount=Decimal("98.76"), currency="usd", provider="unclaimed", status="pending", created_by=user)
    rows = build_platform_usage(platform_context=context()).records
    assert not any(row["metric"] == "revenue" for row in rows)
