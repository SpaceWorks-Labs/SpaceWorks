"""Returning members, account-less desk applications and private lifecycle notices."""
from decimal import Decimal
from unittest.mock import Mock

import pytest

from apps.accounts.models import User
from apps.audit.models import AuditLog
from apps.makerspaces import membership_services
from apps.makerspaces.membership_admission_notifications import notify_admission
from apps.makerspaces.membership_admission_settings import update_settings
from apps.makerspaces.models import MakerspaceMembership, MembershipRequest
from apps.makerspaces.walk_in_services import create_walk_in_member
from apps.payments.models import Payment
from apps.payments.reconciliation import mark_offline
from tests.makerspaces.test_membership_admission_matrix import _setup
from tests.makerspaces.test_membership_admission_api import QUESTION, client
from tests.makerspaces.test_membership_j1 import member_role, user
from tests.module_helpers import disable_module
from tests.return_helpers import settlement_details

pytestmark = pytest.mark.django_db(transaction=True)


@pytest.mark.parametrize("rule", ["once", "each_join"])
@pytest.mark.parametrize("timing", ["before_activation", "after_activation"])
def test_rejoin_dues_rule_records_a_fresh_subject_without_double_charging(rule, timing):
    space, actor, applicant, plan, _ = _setup("open", timing=timing, joining_fee=Decimal("5.00"), rejoin_dues_rule=rule)
    membership_services.request_membership(applicant, space)
    original = MembershipRequest.objects.get(makerspace=space, user=applicant)
    payment = Payment.objects.get(pk=original.admission_payment_id)
    mark_offline(payment, actor, settlement=settlement_details())
    member = MakerspaceMembership.objects.get(makerspace=space, user=applicant)
    membership_services.revoke_membership(actor, member)
    second = membership_services.request_membership(applicant, space)
    returning = MembershipRequest.objects.filter(makerspace=space, user=applicant).first()
    assert returning.pk != original.pk and returning.rejoining
    if rule == "once":
        assert second["outcome"] == "joined" and returning.admission_payment_id is None
        assert Payment.objects.filter(makerspace=space).count() == 1
    else:
        charge = Payment.objects.get(pk=returning.admission_payment_id)
        assert charge.subject_id == returning.pk and charge.amount == Decimal("5.00")
        if timing == "before_activation":
            assert second["state"] == "awaiting_payment"
            own = client(applicant).get(f"/api/v1/member/makerspaces/{space.pk}/admission")
            assert own.status_code == 200 and own.data["id"] == returning.pk
        mark_offline(charge, actor, settlement=settlement_details())
        assert Payment.objects.filter(makerspace=space).count() == 2
    member.refresh_from_db()
    assert member.status == "active"
    assert member.terms.count() == 2


def test_walk_in_paid_before_activation_waits_for_offline_receipt():
    space, actor, _, plan, _ = _setup("open", True, "before_activation")
    row = create_walk_in_member(actor, space, display_name="Desk applicant")
    assert isinstance(row, MembershipRequest) and row.state == "awaiting_payment"
    assert row.user.is_walk_in and not row.user.has_usable_password()
    assert not MakerspaceMembership.objects.filter(user=row.user, makerspace=space).exists()
    mark_offline(row.admission_payment, actor, settlement=settlement_details())
    row.refresh_from_db()
    assert row.state == "active"
    member = MakerspaceMembership.objects.get(user=row.user, makerspace=space)
    assert member.terms.get().plan_id == plan.pk and not member.can_refer


def test_walk_in_answers_and_approval_do_not_give_front_desk_decision_authority():
    space, actor, _, _, _ = _setup("approval", application_schema=QUESTION)
    # The built-in Handover holds issue_direct_loan but no membership-decision action.
    from tests.accounts.account_factories import make_staff
    desk = make_staff(space, username="walk-in-desk", role_slug="handover")
    row = create_walk_in_member(desk, space, display_name="Approval applicant", application_answers={"why": "Learn safely"})
    assert row.state == "requested" and row.approved_at is None
    assert not MakerspaceMembership.objects.filter(makerspace=space, user=row.user).exists()
    membership_services.approve_request(actor, row, member_role(space))
    row.refresh_from_db()
    assert row.state == "active"


def test_walk_in_http_pending_shape_and_closed_refusal_roll_back_person_creation():
    space, actor, _, _, _ = _setup("vouch", application_schema=QUESTION)
    url = f"/api/v1/admin/makerspaces/{space.pk}/walk-in-members"
    schema = client(actor).get(url)
    assert schema.status_code == 200 and schema.data["application_schema"] == QUESTION
    response = client(actor).post(url, {"display_name": "Pending guest", "application_answers": {"why": "Woodworking"}}, format="json")
    assert response.status_code == 201 and response.data["admission_request"]["state"] == "awaiting_vouches"
    update_settings(actor, space, {"join_mode": "closed"})
    count = User.objects.count()
    refused = client(actor).post(url, {"display_name": "Refused guest"}, format="json")
    assert refused.status_code == 400 and refused.data["code"] == "membership_closed"
    assert User.objects.count() == count


@pytest.mark.skip(reason="Feature not in release 0.12.0: apps.accounts.staff_accounts.create_staff_account (separate staff accounts retired by #63/#66)")
def test_membership_off_keeps_core_walk_in_and_staff_invitation_behaviour():
    space, actor, _, _, _ = _setup("closed")
    disable_module(space, "membership")
    conditions = client(actor).get(f"/api/v1/admin/makerspaces/{space.pk}/walk-in-members")
    assert conditions.status_code == 200 and conditions.data["join_mode"] == "open"
    assert conditions.data["application_schema"] is None and conditions.data["joining_fee"] == "0.00"
    member = create_walk_in_member(actor, space, display_name="Core identity")
    assert member.status == "active" and member.user.is_walk_in
    from apps.makerspaces.models import MakerspaceRole
    staff_role = MakerspaceRole.objects.get(makerspace=space, slug="inventory_manager")
    invited = user("module-off-staff")
    from rest_framework.exceptions import ValidationError
    from apps.accounts.staff_accounts import create_staff_account

    with pytest.raises(ValidationError, match="separate staff account"):
        membership_services.invite_membership(actor, space, invited.email, staff_role)
    assert not MakerspaceMembership.objects.filter(user=invited, makerspace=space).exists()
    invited.refresh_from_db()
    assert invited.account_kind == "member"
    staff = create_staff_account(space, name="Core staff", email=invited.email,
                                 roles=[staff_role], created_by=actor)
    assert staff.account_kind == "staff" and staff.pk != invited.pk
    assert staff.makerspace_memberships.get().assigned_role == staff_role


@pytest.mark.parametrize("event", ["awaiting_payment", "payment_due", "declined"])
def test_admission_family_addresses_the_owned_applicant_including_pending_rejoin(
    event, monkeypatch, settings, mailoutbox,
):
    import json
    from apps.integrations.models import NotificationPreference
    from apps.integrations.models_contract import NotificationEnvelope
    from apps.integrations.notification_resolution import resolve
    from apps.integrations.notification_tasks import deliver_envelope
    from django.utils import timezone
    from tests.notification_delivery_helpers import run_outbox
    run_outbox(monkeypatch, settings)
    monkeypatch.setattr("apps.integrations.notification_outbox.enqueue", lambda pk: None)
    space, actor, applicant, _, _ = _setup("approval", True, "before_activation")
    previous = MakerspaceMembership.objects.create(makerspace=space, user=applicant,
        assigned_role=member_role(space), status="revoked", revoked_at=timezone.now())
    result = membership_services.request_membership(applicant, space)
    row = MembershipRequest.objects.get(pk=result["request_id"])
    if event == "declined":
        membership_services.revoke_request(actor, row)
    else:
        membership_services.approve_request(actor, row, member_role(space))
    row.refresh_from_db()
    NotificationPreference.objects.create(makerspace=space, feature="members", channel="email", enabled=True)
    NotificationPreference.objects.create(makerspace=space, feature="members", channel="in_app", enabled=True)
    space.enabled_features = sorted(set(space.enabled_features) | {"notifications.member_inbox"})
    space.save(update_fields=["enabled_features"])
    notify_admission(row, event)
    envelope = NotificationEnvelope.objects.get(source_kind="membership.application", source_id=str(row.pk),
        event=event, audience="requester")
    assert envelope.recipient_id == applicant.pk and envelope.feature == "members"
    assert "application_answers" not in envelope.context
    assert "application_answers" not in json.loads(envelope.message_body)
    assert [target.channel for target in resolve(envelope)] == ["email", "in_app"]
    deliver_envelope.run(envelope.pk)
    assert [message.to for message in mailoutbox] == [[applicant.email]]
    from apps.notifications.models import NotificationInboxRow
    inbox = NotificationInboxRow.objects.get(makerspace=space, event=event)
    assert inbox.user_id == applicant.pk
    assert set(envelope.deliveries.values_list("channel", "state")) == {("email", "sent"), ("in_app", "sent")}
    previous.refresh_from_db()
    assert previous.status == "revoked"  # Delivery never reinstates membership authority.


def test_reapplication_exception_refuses_unrelated_sources_withdrawn_consent_and_wrong_owner(monkeypatch):
    from apps.integrations.models import NotificationPreference
    from apps.integrations.models_contract import NotificationEnvelope
    from apps.integrations.notification_resolution import resolve
    from django.utils import timezone
    monkeypatch.setattr("apps.integrations.notification_outbox.enqueue", lambda pk: None)
    space, actor, applicant, _, _ = _setup("approval", True, "before_activation")
    previous = MakerspaceMembership.objects.create(makerspace=space, user=applicant,
        assigned_role=member_role(space), status="revoked", revoked_at=timezone.now())
    result = membership_services.request_membership(applicant, space)
    row = MembershipRequest.objects.get(pk=result["request_id"])
    NotificationPreference.objects.create(makerspace=space, feature="members", channel="email", enabled=True)
    envelope = NotificationEnvelope.objects.get(source_kind="membership.application", source_id=str(row.pk),
        event="request_pending", audience="requester")
    assert resolve(envelope)
    from apps.notifications.models import MemberNotificationPreference
    mute = MemberNotificationPreference.objects.create(makerspace=space, user=applicant,
        feature="members", channel="email", enabled=False)
    assert resolve(envelope) == []
    mute.delete()
    assert resolve(envelope)
    from datetime import timedelta
    revoked_at = previous.revoked_at
    previous.revoked_at = row.created_at + timedelta(seconds=1)
    previous.save(update_fields=["revoked_at"])
    assert resolve(envelope) == []  # An application from before revocation cannot revive notices.
    previous.revoked_at = revoked_at
    previous.save(update_fields=["revoked_at"])
    assert resolve(envelope)
    previous.receives_notifications = False
    previous.save(update_fields=["receives_notifications"])
    assert resolve(envelope) == []
    previous.receives_notifications = True
    previous.save(update_fields=["receives_notifications"])
    NotificationEnvelope.objects.filter(pk=envelope.pk).update(source_kind="membership.lifecycle")
    assert resolve(envelope) == []
    NotificationEnvelope.objects.filter(pk=envelope.pk).update(source_kind="membership.application", recipient=actor)
    assert resolve(envelope) == []
    NotificationEnvelope.objects.filter(pk=envelope.pk).update(recipient=applicant)
    applicant.access_status = "suspended"
    applicant.save(update_fields=["access_status"])
    assert resolve(envelope) == []


def test_outbound_notice_failure_never_rolls_back_awaiting_payment(monkeypatch):
    space, actor, applicant, _, _ = _setup("approval", True, "before_activation")
    outcome = membership_services.request_membership(applicant, space)
    row = MembershipRequest.objects.get(pk=outcome["request_id"])
    monkeypatch.setattr("apps.operations.notifications_p2.emit", Mock(side_effect=RuntimeError("outbox unavailable")))
    membership_services.approve_request(actor, row, member_role(space))
    row.refresh_from_db()
    assert row.state == "awaiting_payment" and row.admission_payment.status == "pending"
    assert AuditLog.objects.filter(action="membership.application_approved", target_id=str(row.pk)).exists()


def test_configured_core_creation_keeps_the_existing_space_manager_protection():
    from apps.admin_api.services_staff import attach_staff_membership
    from rest_framework.exceptions import ValidationError
    from tests.makerspaces.test_membership_j1 import manager
    space, original, _, _, _ = _setup("open")
    actor = manager(space, "another-admission-manager")
    with pytest.raises(ValidationError):
        attach_staff_membership(actor=actor, makerspace=space, username=original.username,
                                role=member_role(space))
    original_membership = MakerspaceMembership.objects.get(user=original, makerspace=space)
    assert original_membership.assigned_role.slug == "space_manager"
