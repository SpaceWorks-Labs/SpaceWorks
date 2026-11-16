"""Drive real creation, queue, invite, waiver and compensation services."""

import pytest
from django.db import transaction
from django.utils import timezone
from rest_framework.exceptions import NotFound

from apps.audit.models import AuditLog
from apps.events import services
from apps.events.host_waivers import HostWaiverRequired
from apps.events.invites import create_invite, redeem_invite, resolve_for_account
from apps.events.models import EventRegistration, EventTicketType
from apps.events.organization_audience import FEATURE, OrganizationAudienceRefused
from apps.events.promos import create_promo
from apps.events.services_registration_tools import restore_registration
from apps.makerspaces.models import MakerspaceMembership, MakerspaceWaiver
from apps.organizations.models import OrganizationMembership
from apps.payments.models import Payment
from tests.events.organization_audience_helpers import audience_fixture, direct
from tests.events.ticketing_helpers import account, signup

pytestmark = pytest.mark.django_db


@pytest.mark.parametrize("staff", [False, True])
def test_creation_and_cancelled_row_reregistration_recheck_live_membership(staff):
    _, orgs, _, event, manager = audience_fixture()
    user = direct(orgs[0])
    row = services.register(event, member=user, actor=manager if staff else user, staff_registration=staff)
    services.cancel_registration(row, actor=manager)
    OrganizationMembership.objects.filter(user=user).update(status="suspended")
    with pytest.raises(OrganizationAudienceRefused):
        services.register(event, member=user, actor=manager if staff else user, staff_registration=staff)
    row.refresh_from_db()
    assert row.status == "cancelled"
    assert AuditLog.objects.filter(action="event.registration_created").count() == 1


@pytest.mark.parametrize("status", ["registered", "waitlisted", "pending_approval"])
def test_undo_to_every_prior_state_requires_current_eligibility(status):
    _, orgs, _, event, manager = audience_fixture(
        registration_requires_approval=status == "pending_approval", capacity=1 if status == "waitlisted" else 0,
    )
    if status == "waitlisted":
        services.register(event, member=direct(orgs[0], "incumbent"))
    user = direct(orgs[1])
    row = services.register(event, member=user)
    assert row.status == status
    cancelled = services.cancel_registration(row, actor=manager)
    OrganizationMembership.objects.filter(user=user).update(status="suspended")
    with pytest.raises(OrganizationAudienceRefused):
        restore_registration(cancelled, actor=manager)
    row.refresh_from_db(); assert row.status == "cancelled"
    OrganizationMembership.objects.filter(user=user).update(status="active")
    assert restore_registration(row, actor=manager).status == status


def test_explicit_approval_and_manual_promotion_refuse_without_seat_or_charge_side_effects():
    _, orgs, _, event, manager = audience_fixture(registration_requires_approval=True, capacity=1)
    first = services.register(event, member=direct(orgs[0], "first"))
    waiting_user = direct(orgs[1], "waiting")
    waiting = services.register(event, member=waiting_user)
    OrganizationMembership.objects.filter(user=waiting_user).update(status="suspended")
    with pytest.raises(OrganizationAudienceRefused):
        services.approve_registration(waiting, actor=manager)
    waiting.refresh_from_db(); assert waiting.status == "pending_approval"
    services.approve_registration(first, actor=manager)
    OrganizationMembership.objects.filter(user=waiting_user).update(status="active")
    waiting = services.approve_registration(waiting, actor=manager)
    assert waiting.status == "waitlisted"
    OrganizationMembership.objects.filter(user=waiting_user).update(status="suspended")
    services.cancel_registration(first, actor=manager)
    with pytest.raises(OrganizationAudienceRefused):
        services.promote_registration(waiting, actor=manager)
    waiting.refresh_from_db(); assert waiting.status == "waitlisted"
    assert not Payment.objects.filter(subject_type="event_registration", subject_id=waiting.pk).exists()


def test_fifo_skips_ineligible_waiter_and_charges_only_next_eligible_waiter():
    _, orgs, _, event, manager = audience_fixture(capacity=1, payment_amount=10)
    first = services.register(event, member=direct(orgs[0], "incumbent"))
    early_user = direct(orgs[0], "early")
    early = services.register(event, member=early_user)
    later = services.register(event, member=direct(orgs[1], "later"))
    OrganizationMembership.objects.filter(user=early_user).update(status="suspended")
    services.cancel_registration(first, actor=manager)
    early.refresh_from_db(); later.refresh_from_db()
    assert (early.status, later.status) == ("waitlisted", "registered")
    assert not Payment.objects.filter(subject_type="event_registration", subject_id=early.pk).exists()
    assert Payment.objects.get(subject_type="event_registration", subject_id=later.pk).amount == 10
    assert not AuditLog.objects.filter(action="event.registration_promoted", target_id=str(early.pk)).exists()


@pytest.mark.parametrize("operation", ["register", "approve", "promote", "restore", "redeem", "email"])
def test_feature_off_at_each_new_admission_boundary(operation):
    venue, orgs, _, event, manager = audience_fixture(registration_requires_approval=operation in ("approve", "promote"))
    user = direct(orgs[0]); user.email_verified_at = timezone.now(); user.save(update_fields=["email_verified_at"])
    row = services.register(event, member=user)
    invite, code = create_invite(event, actor=manager, email=user.email)
    if operation == "restore":
        row = services.cancel_registration(row, actor=manager)
    if operation == "promote":
        # Create a genuine approval waitlist by filling event capacity before deciding.
        event.capacity = 1; event.save(update_fields=["capacity"])
        another = services.register(event, member=direct(orgs[1], "another"))
        services.approve_registration(another, actor=manager)
        row = services.approve_registration(row, actor=manager)
    venue.enabled_features.remove(FEATURE); venue.save(update_fields=["enabled_features"])
    event.makerspace = venue
    operations = {
        "register": lambda: services.register(event, member=direct(orgs[1], "new")),
        "approve": lambda: services.approve_registration(row, actor=manager),
        "promote": lambda: services.promote_registration(row, actor=manager),
        "restore": lambda: restore_registration(row, actor=manager),
        "redeem": lambda: redeem_invite(event, code, user, actor=user),
        "email": lambda: resolve_for_account(event, user, actor=user),
    }
    with pytest.raises(OrganizationAudienceRefused):
        operations[operation]()


def test_optional_invites_cannot_substitute_for_membership_or_consume_on_failed_admission():
    _, orgs, _, event, manager = audience_fixture()
    outsider = account("outsider")
    invite, code = create_invite(event, actor=manager)
    promo, promo_code = create_promo(event, actor=manager, percent_off=10)
    assert signup(event, outsider, invite_code=code, promo_code=promo_code).status_code == 403
    with pytest.raises(OrganizationAudienceRefused):
        redeem_invite(event, code, outsider, actor=outsider)
    invite.refresh_from_db(); promo.refresh_from_db()
    assert (invite.uses, promo.uses) == (0, 0)
    user = direct(orgs[0])
    assert signup(event, user, invite_code=code).status_code == 201
    invite.refresh_from_db(); assert invite.uses == 1
    assert signup(event, user, invite_code=code).status_code == 201
    invite.refresh_from_db(); assert invite.uses == 1
    assert signup(event, direct(orgs[1], "no-invite")).status_code == 201


@pytest.mark.parametrize("verified", [False, True])
def test_bound_code_and_codefree_optional_email_invite_require_verified_identity(verified):
    _, orgs, _, event, manager = audience_fixture()
    user = direct(orgs[0])
    if verified:
        user.email_verified_at = timezone.now(); user.save(update_fields=["email_verified_at"])
    invite, code = create_invite(event, actor=manager, email=user.email, max_uses=2)
    if not verified:
        assert signup(event, user, invite_code=code).status_code == 404
    else:
        assert signup(event, user, invite_code=code).status_code == 201
        services.cancel_registration(event.registrations.get(), actor=manager)
    assert signup(event, user).status_code == 201
    invite.refresh_from_db(); assert invite.uses == (2 if verified else 0)


def test_host_waiver_explicit_self_consent_staff_refusal_and_idempotent_repair():
    venue, orgs, _, event, manager = audience_fixture()
    waiver = MakerspaceWaiver.objects.create(makerspace=venue, version="v1", body="Host terms", is_active=True)
    user = direct(orgs[0])
    for data in ({}, {"host_waiver_id": waiver.pk, "host_waiver_version": "v1"},
                 {"host_waiver_id": waiver.pk, "host_waiver_version": "old", "host_waiver_accepted": True}):
        assert signup(event, user, **data).status_code == 400
    with pytest.raises(HostWaiverRequired):
        services.register(event, member=user, actor=manager, staff_registration=True,
                          host_waiver_id=waiver.pk, host_waiver_version="v1", host_waiver_accepted=True)
    consent = {"host_waiver_id": waiver.pk, "host_waiver_version": "v1", "host_waiver_accepted": True}
    assert signup(event, user, **consent).status_code == 201
    row = event.registrations.get()
    assert row.host_waiver_id == waiver.pk
    # Historical missing-stamp repair runs through the real duplicate request, no code use.
    EventRegistration.objects.filter(pk=row.pk).update(host_waiver=None, host_waiver_accepted_at=None, host_waiver_version_accepted=None)
    assert signup(event, user, **consent).status_code == 201
    row.refresh_from_db(); assert row.host_waiver_id == waiver.pk
    assert AuditLog.objects.filter(action="event.host_waiver_accepted").count() == 2
    assert "Host terms" not in str(list(AuditLog.objects.values_list("meta", flat=True)))


def test_member_ticket_type_is_not_unlocked_by_organization_membership():
    venue, orgs, _, event, manager = audience_fixture()
    ticket = EventTicketType.objects.create(event=event, makerspace=venue, name="Members", audience="member")
    response = signup(event, direct(orgs[0]), ticket_type_id=ticket.pk)
    assert response.status_code in (403, 404)
    assert not event.registrations.exists()


def test_host_member_current_acceptance_needs_no_duplicate_stamp():
    from tests.events.organization_audience_helpers import local
    venue, _, _, event, _ = audience_fixture()
    waiver = MakerspaceWaiver.objects.create(makerspace=venue, version="v1", body="Host terms", is_active=True)
    user = local(venue)
    MakerspaceMembership.objects.filter(user=user).update(
        accepted_waiver=waiver, waiver_accepted_at=timezone.now(), waiver_version_accepted="v1")
    assert signup(event, user).status_code == 201
    assert event.registrations.get().host_waiver_id is None
    assert not AuditLog.objects.filter(action="event.host_waiver_accepted").exists()


def test_partner_registration_requires_collaboration_partner_waiver_and_organization_proof():
    from django.urls import reverse
    from apps.events.models import EventCollaborator
    from tests.events.collab_helpers import client_for, make_member
    from tests.events.ticketing_helpers import event_space
    venue, orgs, _, event, _ = audience_fixture()
    partner = event_space("unrelated-partner", membership=True)
    visitor = make_member(partner)
    EventCollaborator.objects.create(event=event, makerspace=partner, status="accepted")
    path = reverse("member-collaborative-event-register", args=[partner.pk, event.pk])
    assert client_for(visitor).post(path, {}, format="json").status_code == 403
    OrganizationMembership.objects.create(user=visitor, organization=orgs[0], status="active")
    partner_waiver = MakerspaceWaiver.objects.create(makerspace=partner, version="p1", body="Partner terms", is_active=True)
    assert client_for(visitor).post(path, {}, format="json").status_code == 403
    MakerspaceMembership.objects.filter(user=visitor, makerspace=partner).update(
        accepted_waiver=partner_waiver, waiver_version_accepted="p1", waiver_accepted_at=timezone.now())
    host = MakerspaceWaiver.objects.create(makerspace=venue, version="h1", body="Host terms", is_active=True)
    consent = {"host_waiver_id": host.pk, "host_waiver_version": "h1", "host_waiver_accepted": True}
    assert client_for(visitor).post(path, consent, format="json").status_code == 201
    row = event.registrations.get()
    assert row.registered_via_makerspace_id == partner.pk and row.payment_via_makerspace_id == partner.pk
    assert row.host_waiver_id == host.pk
