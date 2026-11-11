"""Decision 223 (c)(f): a guest-pass holder in the lending paths -- borrowing modes, the on-site due
cap, the reviewed-issue gate and mandatory deposit, sponsor liability and the incident record."""
from datetime import timedelta

import pytest
from django.utils import timezone

from apps.audit.models import AuditLog
from apps.hardware_requests import guest_lending, guest_liability
from apps.hardware_requests.models import HardwareRequest, HardwareRequestItem, RequesterAccountability
from apps.makerspaces import guest_pass_issue
from apps.makerspaces.guest_pass_policy import GuestPassError
from apps.makerspaces.models import GuestPass, GuestPassPolicy, MakerspaceWaiver
from tests.makerspaces.test_guest_passes import _space, _sponsor
from tests.makerspaces.test_membership_j1 import manager, user
from tests.return_helpers import make_product

pytestmark = pytest.mark.django_db(transaction=True)


def _guest_with_pass(makerspace, name="lend-guest", **policy):
    if policy:
        GuestPassPolicy.objects.filter(makerspace=makerspace).update(**policy)
    guest = user(name)
    row, _ = guest_pass_issue.issue_staff_pass(manager(makerspace, f"{name}-staff"), makerspace, guest)
    return guest, row


def _loan(makerspace, requester, status=HardwareRequest.Status.ACCEPTED, **fields):
    product = make_product(makerspace, f"Drill {requester.pk}")
    loan = HardwareRequest.objects.create(
        makerspace=makerspace, requester=requester, requester_username=requester.username, status=status, **fields)
    HardwareRequestItem.objects.create(request=loan, product=product, requested_quantity=1, accepted_quantity=1)
    return loan


def _incidents_on(makerspace):
    makerspace.enabled_features = sorted(set(makerspace.enabled_features or []) | {"safety.incidents"})
    makerspace.save(update_fields=["enabled_features"])


def test_planning_admits_a_pass_holder_without_presence_or_waiver_and_refuses_a_stranger():
    makerspace = _space("lend-plan")
    MakerspaceWaiver.objects.create(makerspace=makerspace, body="x", version="v1", is_active=True)
    guest, row = _guest_with_pass(makerspace)
    admitted = guest_lending.admit_borrower(makerspace, guest, planning=True)
    assert admitted.guest_pass.pk == row.pk and admitted.membership is None
    from apps.presence.guard import MemberPresenceRequired
    with pytest.raises(MemberPresenceRequired):
        guest_lending.admit_borrower(makerspace, user("lend-stranger"), planning=True)


def test_mode_none_refuses_borrowing_with_guest_pass_no_borrow():
    makerspace = _space("lend-none")
    guest, _row = _guest_with_pass(makerspace, guest_borrowing_mode="none")
    with pytest.raises(GuestPassError) as refused:
        guest_lending.admit_borrower(makerspace, guest, planning=True)
    assert refused.value.error_code == "guest_pass_no_borrow"


def test_on_site_due_is_clamped_to_the_pass_end_and_a_staff_entered_due_past_it_is_refused():
    makerspace = _space("lend-cap")
    guest, row = _guest_with_pass(makerspace)
    far = row.valid_until + timedelta(days=5)
    assert guest_lending.cap_due(makerspace, guest, far) == row.valid_until
    soon = row.valid_until - timedelta(minutes=5)
    assert guest_lending.cap_due(makerspace, guest, soon) == soon
    with pytest.raises(GuestPassError) as take_home:
        guest_lending.cap_due(makerspace, guest, far, staff_entered=True)
    assert take_home.value.error_code == "guest_pass_on_site_only"


def test_due_is_never_capped_for_a_member_or_a_full_borrowing_pass():
    makerspace = _space("lend-nocap")
    member = _sponsor(makerspace, "lend-member")
    due = timezone.now() + timedelta(days=9)
    assert guest_lending.cap_due(makerspace, member, due) == due
    guest, _row = _guest_with_pass(makerspace, "full-guest", guest_borrowing_mode="full_with_deposit")
    assert guest_lending.cap_due(makerspace, guest, due) == due


def test_reviewed_issue_gate_needs_a_live_pass_borrowing_and_the_waiver():
    makerspace = _space("lend-gate")
    with pytest.raises(GuestPassError) as no_pass:
        guest_lending.guest_issue_gate(_loan(makerspace, user("gate-stranger")), manager(makerspace))
    assert no_pass.value.error_code == "guest_pass_required"
    MakerspaceWaiver.objects.create(makerspace=makerspace, body="x", version="v1", is_active=True)
    guest, row = _guest_with_pass(makerspace)
    from apps.presence.guard import WaiverAcceptanceRequired
    with pytest.raises(WaiverAcceptanceRequired):
        guest_lending.guest_issue_gate(_loan(makerspace, guest), manager(makerspace))
    from apps.makerspaces.guest_pass_lifecycle import stamp_waiver
    stamp_waiver(guest, row)
    assert guest_lending.guest_issue_gate(_loan(makerspace, guest), manager(makerspace)).pk == row.pk


def test_reviewed_issue_gate_ignores_members():
    makerspace = _space("lend-gate-member")
    member = _sponsor(makerspace, "gate-member")
    assert guest_lending.guest_issue_gate(_loan(makerspace, member), manager(makerspace)) is None


def test_full_with_deposit_refuses_an_item_with_no_deposit_set():
    makerspace = _space("lend-deposit")
    guest, _row = _guest_with_pass(makerspace, guest_borrowing_mode="full_with_deposit")
    loan = _loan(makerspace, guest)
    with pytest.raises(GuestPassError) as refused:
        guest_lending.require_guest_deposit(loan, manager(makerspace), guest_lending.borrowing_pass(makerspace, guest))
    assert refused.value.error_code == "guest_pass_deposit_required"


def test_sponsor_pays_setting_routes_the_charge_to_the_sponsor_and_is_audited():
    makerspace = _space("lend-liable")
    sponsor, guest = _sponsor(makerspace), user("liable-guest")
    guest_pass_issue.issue_sponsored_pass(sponsor, makerspace, guest)
    loan = _loan(makerspace, guest, issued_at=timezone.now())
    assert guest_liability.liable_member(loan).pk == guest.pk  # default: the guest is accountable
    GuestPassPolicy.objects.filter(makerspace=makerspace).update(sponsored_liability="sponsor")
    assert guest_liability.liable_member(loan).pk == sponsor.pk
    from apps.hardware_requests.loan_charges_common import _get_or_create
    from apps.payments.pricing.quotes import Quote
    from apps.payments.pricing.resolver import rate_card
    card = rate_card(makerspace, "loans")
    priced = Quote(domain="loans", currency=card.currency, lines=(), mode=card.mode)
    payment, created = _get_or_create(loan, "loan_deposit", priced, manager(makerspace), "Deposit")
    assert created and payment.member_id == sponsor.pk
    entry = AuditLog.objects.get(makerspace=makerspace, action="membership.guest_pass_charge_redirected")
    assert entry.meta["guest_id"] == guest.pk and entry.meta["sponsor_id"] == sponsor.pk


def test_a_non_sponsored_guest_is_never_redirected_to_a_sponsor():
    makerspace = _space("lend-day")
    GuestPassPolicy.objects.filter(makerspace=makerspace).update(sponsored_liability="sponsor")
    guest, _row = _guest_with_pass(makerspace)
    assert guest_liability.liable_member(_loan(makerspace, guest, issued_at=timezone.now())).pk == guest.pk


def test_damage_row_records_an_incident_on_the_sponsor_and_notifies_the_sponsor():
    from apps.integrations.models_contract import NotificationEnvelope
    from apps.maintenance.incidents.models import Incident
    makerspace = _space("lend-incident")
    _incidents_on(makerspace)
    sponsor, guest = _sponsor(makerspace), user("incident-guest")
    row, _ = guest_pass_issue.issue_sponsored_pass(sponsor, makerspace, guest)
    loan = _loan(makerspace, guest, issued_at=timezone.now())
    accountability = RequesterAccountability.objects.create(
        requester=guest, request=loan, makerspace=makerspace, issue_type="damaged", quantity=1,
        created_by=manager(makerspace))
    guest_liability.on_accountability_created(accountability.pk)
    incident = Incident.objects.get(makerspace=makerspace, guest_pass=row)
    assert incident.sponsor_user_id == sponsor.pk and incident.involved_user_id == guest.pk
    assert incident.loan_id == loan.pk
    assert NotificationEnvelope.objects.filter(
        makerspace_id=makerspace.pk, event="guest_pass_sponsor_notice", recipient_id=sponsor.pk).exists()


def test_outstanding_items_at_pass_end_record_one_incident_and_one_notice():
    from apps.maintenance.incidents.models import Incident
    makerspace = _space("lend-outstanding")
    _incidents_on(makerspace)
    sponsor, guest = _sponsor(makerspace), user("outstanding-guest")
    row, _ = guest_pass_issue.issue_sponsored_pass(sponsor, makerspace, guest)
    loan = _loan(makerspace, guest, status=HardwareRequest.Status.ISSUED, issued_at=timezone.now() - timedelta(hours=2))
    GuestPass.objects.filter(pk=row.pk).update(
        valid_from=timezone.now() - timedelta(hours=3), valid_until=timezone.now() - timedelta(minutes=1))
    assert guest_liability.record_outstanding_at_pass_end(makerspace=makerspace) == 1
    assert guest_liability.record_outstanding_at_pass_end(makerspace=makerspace) == 0  # deduped on (pass, loan)
    assert Incident.objects.filter(guest_pass=row, loan=loan).count() == 1


def test_sponsored_damage_is_recorded_even_while_the_incident_register_is_off():
    """Decision 226(f): retained (not shown) while safety.incidents is off; the sponsor is still told."""
    from apps.integrations.models_contract import NotificationEnvelope
    from apps.maintenance.incidents.models import Incident
    makerspace = _space("lend-incident-off")
    sponsor, guest = _sponsor(makerspace), user("incident-off-guest")
    row, _ = guest_pass_issue.issue_sponsored_pass(sponsor, makerspace, guest)
    loan = _loan(makerspace, guest, issued_at=timezone.now())
    accountability = RequesterAccountability.objects.create(
        requester=guest, request=loan, makerspace=makerspace, issue_type="damaged", quantity=1,
        created_by=manager(makerspace))
    guest_liability.on_accountability_created(accountability.pk)
    assert Incident.objects.filter(makerspace=makerspace, guest_pass=row, sponsor_user=sponsor).count() == 1
    assert NotificationEnvelope.objects.filter(
        makerspace_id=makerspace.pk, event="guest_pass_sponsor_notice", recipient_id=sponsor.pk).exists()
    from apps.maintenance.incidents.services import record_incident
    assert record_incident(makerspace, title="x", kind="incident") is None  # the default stays inert


def test_on_site_cap_rolls_back_to_the_last_close_inside_the_pass_window(monkeypatch):
    makerspace = _space("lend-cap-closed")
    guest, row = _guest_with_pass(makerspace)
    close = row.valid_until - timedelta(hours=2)
    monkeypatch.setattr(guest_lending, "previous_close", lambda _space, _at: close)
    far = row.valid_until + timedelta(days=5)
    assert guest_lending.cap_due(makerspace, guest, far) == close
    # a close before the pass even started is not "inside the window": keep the pass end
    monkeypatch.setattr(guest_lending, "previous_close", lambda _space, _at: row.valid_from - timedelta(hours=1))
    assert guest_lending.cap_due(makerspace, guest, far) == row.valid_until
