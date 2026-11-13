"""Personal charts cannot be retargeted; core money survives membership/module changes."""

from datetime import timedelta
from decimal import Decimal

import pytest
from django.utils import timezone

from apps.events.models import Event
from apps.hardware_requests.models import HardwareRequest, PublicToolLoan, ReturnEvent
from apps.machines.models import Machine, MachineType, MachineUsageEntry
from apps.makerspaces.models import MakerspaceMembership
from apps.operations.report_validation import validate_chart_spec
from apps.payments.models import Payment
from apps.payments.services import create_payment
from tests.fixed_roles.helpers import assign_builtin_roles, staff_account
from tests.modules.family_helpers import account, client, family_space
from .de_helpers_m1f2 import booking, registration

pytestmark = pytest.mark.django_db


def lab(slug="my-usage-m1f4"):
    return family_space(slug, "membership", "machines", "bookings", "events", "request_workflow", loans=True)


def member(space, name):
    actor = account(name)
    assign_builtin_roles(actor, space, "member")
    return actor


def url(space):
    return f"/api/v1/member/makerspaces/{space.pk}/my-usage"


def charge(space, actor, *, amount="10.00", currency="usd", status="pending"):
    request = HardwareRequest.objects.create(makerspace=space, requester=actor, status="draft")
    payment = create_payment(makerspace=space, member=actor, subject_type=Payment.SubjectType.LOAN_DEPOSIT,
                             subject_id=request.pk, amount=Decimal(amount), currency=currency, created_by=actor)
    if status != "pending":
        Payment.objects.filter(pk=payment.pk).update(status=status)
    return payment


def seed(space, actor, *, hours="2.50"):
    now = timezone.now()
    HardwareRequest.objects.create(makerspace=space, requester=actor, status="issued", issued_at=now)
    reviewed = HardwareRequest.objects.create(makerspace=space, requester=actor, status="returned", issued_at=now, closed_at=now)
    PublicToolLoan.objects.create(makerspace=space, requester=actor, request=reviewed,
                                 target_type="product", target_id=1, target_label="Own drill",
                                 status="returned", returned_at=now)
    kind, _ = MachineType.objects.get_or_create(makerspace=space, slug="laser", defaults={"name": "Laser"})
    machine = Machine.objects.create(makerspace=space, machine_type=kind, name=f"Machine {actor.pk}")
    MachineUsageEntry.objects.create(machine=machine, member=actor, hours=hours, started_at=now,
                                     note="Private note must not escape")
    booking(space, actor, start=now, status="confirmed")
    event = Event.objects.create(makerspace=space, title="Event", starts_at=now, ends_at=now + timedelta(hours=1))
    registration(event, actor, at=now, status="attended", discount="0.00")
    charge(space, actor)
    charge(space, actor, currency="inr", amount="20.00")
    charge(space, actor, amount="3.00", status="paid_online")
    return machine


def test_usage_contains_only_caller_and_selected_tenant_and_never_staff_reports(monkeypatch):
    space, other = lab(), lab("my-usage-foreign")
    actor, stranger = member(space, "my-usage-owner"), member(space, "my-usage-stranger")
    own_machine = seed(space, actor)
    seed(space, stranger, hours="99.00")
    seed(other, actor, hours="55.00")
    # Unknown attribution is never inferred from who logged the usage.
    MachineUsageEntry.objects.create(machine=own_machine, logged_by=actor, hours="88.00")

    def no_staff_report(*args, **kwargs):
        raise AssertionError("Personal usage must not dispatch staff reports")

    monkeypatch.setattr("apps.operations.reports.report_data", no_staff_report)
    response = client(actor).get(url(space), {"member_id": stranger.pk, "user_id": stranger.pk, "makerspace_id": other.pk})
    assert response.status_code == 200, response.data
    data = response.data
    assert data["usage_available"] is True
    assert data["loans"]["count"] == 2  # Direct + its workflow request is one handover.
    assert data["loans"]["returned_count"] == 1 and data["loans"]["currently_out"] == 1
    assert sum(row["issued_count"] for row in data["loans"]["monthly"]["rows"]) == 2
    assert Decimal(data["machines"]["hours"]) == Decimal("2.50")
    assert {row["machine_id"] for row in data["machines"]["top_machines"]["rows"]} == {own_machine.pk}
    assert data["bookings"]["count"] == 1
    assert data["events"]["attended_count"] == 1
    assert data["payments"]["paid_by_currency"] == {"usd": "3.00"}
    assert data["payments"]["outstanding_by_currency"] == {"inr": "20.00", "usd": "10.00"}
    assert response["Cache-Control"] == "private, no-store"
    assert "Private" not in str(data) and stranger.email not in str(data)


def test_module_off_omits_its_usage_and_membership_off_leaves_core_payments():
    space, actor = lab(), account("my-usage-module-member")
    assign_builtin_roles(actor, space, "member")
    seed(space, actor)
    space.enabled_modules = [module for module in space.enabled_modules if module not in {"machines", "bookings", "events", "payments"}]
    space.save(update_fields=["enabled_modules"])
    data = client(actor).get(url(space)).data
    assert data["usage_available"] is True
    assert not {"machines", "bookings", "events"} & data.keys()
    assert data["payments"]["outstanding_by_currency"]
    space.enabled_modules.remove("membership")
    space.save(update_fields=["enabled_modules"])
    response = client(actor).get(url(space))
    assert response.status_code == 200, response.data
    assert set(response.data) == {"usage_available", "payments"}
    assert response.data["usage_available"] is False
    # Existing activity remains gated; this exception is only the payment summary.
    assert client(actor).get(f"/api/v1/member/makerspaces/{space.pk}/activity").status_code == 404


def test_account_only_borrower_can_read_only_their_money():
    space, actor, other = lab(), account("usage-account-only"), account("usage-other-account")
    charge(space, actor, amount="7.00")
    charge(space, other, amount="111.00")
    response = client(actor).get(url(space))
    assert response.status_code == 200, response.data
    assert set(response.data) == {"usage_available", "payments"}
    assert response.data["payments"]["outstanding_by_currency"] == {"usd": "7.00"}
    assert client(account("usage-no-charge")).get(url(space)).status_code == 403


def test_revoked_membership_never_gets_usage_or_old_money():
    space, actor = lab(), account("usage-revoked")
    membership = assign_builtin_roles(actor, space, "member")
    charge(space, actor)
    MakerspaceMembership.objects.filter(pk=membership.pk).update(status="revoked")
    assert client(actor).get(url(space)).status_code == 403


@pytest.mark.parametrize("access", ["restricted", "suspended"])
def test_restricted_accounts_can_read_only_their_own_money(access):
    # Decision 260 (G-1): paying a debt is how a restriction is cleared, so a restricted or suspended
    # account still reads the payment summary in its own name -- and nothing else.
    space, actor = lab(), account("usage-account-restricted")
    charge(space, actor)
    actor.access_status = access
    actor.save(update_fields=["access_status"])
    response = client(actor).get(url(space))
    assert response.status_code == 200, response.data
    assert set(response.data) == {"usage_available", "payments"}
    assert response.data["usage_available"] is False


def test_unrelated_and_unservable_tenant_usage_is_refused():
    space, other, actor = lab(), lab("usage-unrelated"), account("usage-boundary")
    assign_builtin_roles(actor, space, "member")
    assert client(actor).get(url(other)).status_code == 403
    other.lifecycle_state = "migrated_out"
    other.save(update_fields=["lifecycle_state"])
    assert client(actor).get(url(other)).status_code == 404


def test_monthly_charts_use_tenant_zone_and_exclude_cancelled_bookings():
    from datetime import datetime, timezone as dt_timezone
    from unittest.mock import patch

    space, actor = lab(), account("usage-local-calendar")
    assign_builtin_roles(actor, space, "member")
    space.timezone = "Asia/Kolkata"
    space.save(update_fields=["timezone"])
    at = datetime(2026, 9, 30, 20, tzinfo=dt_timezone.utc)
    for status in ("confirmed", "cancelled"):
        booking(space, actor, start=at, status=status)
    kind = MachineType.objects.create(makerspace=space, slug="calendar-laser", name="Laser")
    machine = Machine.objects.create(makerspace=space, machine_type=kind, name="Calendar laser")
    with patch("django.utils.timezone.now", return_value=at):
        # Explicit start takes precedence; older attributed entries use creation time.
        MachineUsageEntry.objects.create(machine=machine, member=actor, hours="1.25",
                                         started_at=at - timedelta(hours=6))
        MachineUsageEntry.objects.create(machine=machine, member=actor, hours="2.50")
        MachineUsageEntry.objects.create(machine=machine, logged_by=actor, hours="99.00")
    data = client(actor).get(url(space)).data
    assert data["bookings"]["monthly"]["rows"] == [{"period": "2026-10-01", "count": 1}]
    assert {row["period"]: Decimal(row["hours"]) for row in data["machines"]["monthly"]["rows"]} == {
        "2026-09-01": Decimal("1.25"), "2026-10-01": Decimal("2.50"),
    }
    assert Decimal(data["machines"]["hours"]) == Decimal("3.75")


def test_chart_specs_reference_only_the_returned_fields():
    space, actor = lab(), account("usage-specs")
    assign_builtin_roles(actor, space, "member")
    seed(space, actor)
    data = client(actor).get(url(space)).data
    charts = [data["loans"]["monthly"], data["machines"]["monthly"], data["machines"]["top_machines"],
              data["bookings"]["monthly"], data["events"]["chart"], data["payments"]["totals"]]
    for chart in charts:
        assert chart["rows"]
        validate_chart_spec(chart["chart_spec"], tuple(chart["rows"][0]))


def test_partial_returns_bucket_by_event_time_and_direct_returns_count_once():
    from unittest.mock import patch
    from tests.return_helpers import make_return_evidence
    from datetime import datetime, timezone as dt_timezone

    space, actor = lab(), account("usage-return-events")
    assign_builtin_roles(actor, space, "member")
    space.timezone = "UTC"
    space.save(update_fields=["timezone"])
    issued_at = datetime(2026, 8, 1, tzinfo=dt_timezone.utc)
    event_at = datetime(2026, 9, 1, tzinfo=dt_timezone.utc)
    closed_at = datetime(2026, 10, 1, tzinfo=dt_timezone.utc)
    request = HardwareRequest.objects.create(makerspace=space, requester=actor, status="returned", issued_at=issued_at, closed_at=closed_at)
    PublicToolLoan.objects.create(makerspace=space, requester=actor, request=request,
                                 target_type="product", target_id=1, target_label="Drill", status="returned", returned_at=closed_at)
    for at in (event_at, closed_at):
        evidence = make_return_evidence(space, actor)
        with patch("django.utils.timezone.now", return_value=at):
            ReturnEvent.objects.create(makerspace=space, request=request, evidence=evidence, actor=actor, remark="Returned")
    data = client(actor).get(url(space)).data
    by_month = {row["period"]: row["return_events"] for row in data["loans"]["monthly"]["rows"]}
    assert by_month["2026-09-01"] == 1 and by_month["2026-10-01"] == 1
    assert sum(by_month.values()) == 2


def test_paid_totals_combine_online_and_receipted_offline_money_per_currency():
    from apps.payments.reconciliation import mark_offline
    from tests.return_helpers import settlement_details

    space, actor = lab(), account("usage-paid-member")
    assign_builtin_roles(actor, space, "member")
    staff = staff_account(space, "usage-payment-staff", "space_manager")
    charge(space, actor, amount="3.00", status="paid_online")
    offline = charge(space, actor, amount="2.00")
    mark_offline(offline, staff, settlement_details())
    charge(space, actor, currency="inr", amount="7.00", status="paid_online")
    data = client(actor).get(url(space)).data
    assert data["payments"]["paid_by_currency"] == {"inr": "7.00", "usd": "5.00"}
    assert data["payments"]["outstanding_by_currency"] == {}
