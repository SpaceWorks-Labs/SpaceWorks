"""Consent renewal repairs owned rows after cutoff without readmitting participants."""

from datetime import timedelta

import pytest
from django.urls import reverse
from django.utils import timezone

from apps.audit.models import AuditLog
from apps.events import services
from apps.events.exceptions import EventInvalidTransition, RegistrationClosed
from apps.events.host_waivers import HostWaiverRequired
from apps.events.models import Event, EventRegistration
from apps.events.organization_audience import FEATURE, OrganizationAudienceRefused
from apps.makerspaces.waiver_services import publish_waiver
from apps.organizations.models import OrganizationMembership
from apps.payments.models import Payment
from tests.events.collab_helpers import client_for, collaborate
from tests.events.organization_audience_helpers import audience_fixture, direct, local
from tests.events.ticketing_helpers import signup

pytestmark = pytest.mark.django_db

FORM = [{"id": "reason", "label": "Reason", "type": "short_text", "options": [], "required": True}]


def consent(waiver):
    return {"host_waiver_id": waiver.pk, "host_waiver_version": waiver.version, "host_waiver_accepted": True}


def unchanged_fields(row):
    return {field.attname: getattr(row, field.attname) for field in row._meta.concrete_fields
            if not field.name.startswith("host_waiver")}


def queued_fixture(operation="approve", route="public", cutoff="explicit"):
    venue, orgs, sources, event, manager = audience_fixture(
        registration_requires_approval=operation != "automatic", capacity=1,
        custom_form=FORM, payment_amount=12,
    )
    old = publish_waiver(manager, venue, "Original host terms", "v1")
    if operation != "approve":
        incumbent = direct(orgs[1], "incumbent")
        first = services.register(event, member=incumbent, actor=incumbent,
                                  custom_answers={"reason": "original"}, **consent(old))
        if operation == "manual":
            services.approve_registration(first, actor=manager)
    user = direct(orgs[0]) if route == "public" else local(sources[0])
    partner = None
    if route == "partner":
        partner = sources[0]
        partner.enabled_modules += ["membership"]
        partner.save(update_fields=["enabled_modules"])
        collaborate(event, partner)
    row = services.register(event, member=user, actor=user, collaborative=partner is not None,
                            via_makerspace=partner, custom_answers={"reason": "saved"}, **consent(old))
    if operation == "manual":
        row = services.approve_registration(row, actor=manager)
    if cutoff == "explicit":
        event.registration_cutoff_at = timezone.now()
        event.save(update_fields=["registration_cutoff_at"])
    else:
        event.registration_cutoff_lead_minutes = 2880
        event.save(update_fields=["registration_cutoff_lead_minutes"])
    new = publish_waiver(manager, venue, "Renewed host terms", "v2")
    return venue, event, manager, user, row, new, partner


@pytest.mark.parametrize("operation", ["approve", "manual", "automatic"])
@pytest.mark.parametrize("route", ["public", "partner"])
@pytest.mark.parametrize("cutoff", ["explicit", "lead"])
def test_queued_self_consent_after_cutoff_preserves_state_then_allows_admission(operation, route, cutoff):
    _, event, manager, user, row, waiver, partner = queued_fixture(operation, route, cutoff)
    before = unchanged_fields(row)
    decide = {"approve": services.approve_registration, "manual": services.promote_registration}
    if operation == "automatic":
        # An internal step of locked commands: run it inside the shared write boundary.
        from apps.events.services_write_boundary import write_boundary
        with write_boundary(event, actor=manager):
            assert services.promote_automatically(event, manager) == []
    else:
        with pytest.raises(HostWaiverRequired):
            decide[operation](row, actor=manager)
    payment_count = Payment.objects.count()
    audit_count = AuditLog.objects.count()
    path = reverse("member-collaborative-event-register", args=[partner.pk, event.pk]) if partner else None
    # Required form answers are omitted; this is consent only, through the real HTTP path.
    response = client_for(user).post(path, consent(waiver), format="json") if path else signup(event, user, **consent(waiver))
    assert response.status_code == 201, response.data
    row.refresh_from_db()
    # Consent repair keeps the established status-only registration response.
    assert response.data == {"status": row.status}
    assert unchanged_fields(row) == before
    assert row.host_waiver_id == waiver.pk and row.host_waiver_version_accepted == "v2"
    assert row.host_waiver_accepted_at is not None
    assert Payment.objects.count() == payment_count
    assert AuditLog.objects.count() == audit_count + 1
    acceptance = AuditLog.objects.filter(action="event.host_waiver_accepted", target_id=str(row.pk)).latest("id")
    assert acceptance.actor_id == user.pk
    assert acceptance.meta["host_waiver_id"] == waiver.pk
    assert "Renewed host terms" not in str(acceptance.meta)
    # Replaying acceptance neither adds another audit nor overwrites saved answers.
    replay = {**consent(waiver), "custom_answers": {"reason": "overwrite attempt"}}
    response = client_for(user).post(path, replay, format="json") if path else signup(event, user, **replay)
    assert response.status_code == 201, response.data
    row.refresh_from_db()
    assert unchanged_fields(row) == before and AuditLog.objects.count() == audit_count + 1
    assert Payment.objects.count() == payment_count
    if operation != "approve":
        event.capacity = 2
        event.save(update_fields=["capacity"])
    if operation == "automatic":
        from apps.events.services_write_boundary import write_boundary
        with write_boundary(event, actor=manager):
            assert [item.pk for item in services.promote_automatically(event, manager)] == [row.pk]
    else:
        assert decide[operation](row, actor=manager).status == "registered"
    row.refresh_from_db()
    assert row.status == "registered"
    assert Payment.objects.get(subject_type="event_registration", subject_id=row.pk).amount == 12


@pytest.mark.parametrize("failure", ["missing", "stale", "declined", "staff", "other_actor",
                                    "ineligible", "feature_off"])
def test_after_cutoff_repair_cannot_forge_consent_or_bypass_eligibility(failure):
    venue, event, manager, user, row, waiver, _ = queued_fixture()
    before = unchanged_fields(row)
    old_waiver_id = row.host_waiver_id
    payload = consent(waiver)
    actor, staff = user, False
    expected = HostWaiverRequired
    if failure == "missing":
        payload = {}
    elif failure == "stale":
        payload["host_waiver_version"] = "v1"
    elif failure == "declined":
        payload["host_waiver_accepted"] = False
    elif failure in ("staff", "other_actor"):
        actor, staff = manager, failure == "staff"
        expected = RegistrationClosed
    elif failure == "ineligible":
        OrganizationMembership.objects.filter(user=user).update(status="suspended")
        expected = OrganizationAudienceRefused
    elif failure == "feature_off":
        venue.enabled_features.remove(FEATURE)
        venue.save(update_fields=["enabled_features"])
        expected = OrganizationAudienceRefused
    audit_count, payment_count = AuditLog.objects.count(), Payment.objects.count()
    with pytest.raises(expected):
        services.register(event, member=user, actor=actor, staff_registration=staff,
                          repair_duplicate=True, **payload)
    row.refresh_from_db()
    assert unchanged_fields(row) == before and row.host_waiver_id == old_waiver_id
    assert (AuditLog.objects.count(), Payment.objects.count()) == (audit_count, payment_count)


@pytest.mark.parametrize("state", ["new", "cancelled", "rejected", "attended", "event_cancelled", "ended"])
def test_consent_repair_does_not_reopen_signup_or_terminal_state(state):
    _, event, manager, user, row, waiver, _ = queued_fixture()
    expected = RegistrationClosed
    if state == "new":
        user = direct(OrganizationMembership.objects.get(user=user).organization, "new-user")
    elif state in ("cancelled", "rejected", "attended"):
        row.status = state
        row.save(update_fields=["status"])
    elif state == "event_cancelled":
        event.status = Event.Status.CANCELLED
        event.save(update_fields=["status"])
        expected = EventInvalidTransition
    else:
        event.starts_at = timezone.now() - timedelta(hours=2)
        event.ends_at = timezone.now() - timedelta(hours=1)
        event.registration_cutoff_at = event.starts_at
        event.save(update_fields=["starts_at", "ends_at", "registration_cutoff_at"])
        expected = EventInvalidTransition
    before = unchanged_fields(row)
    audit_count, payment_count = AuditLog.objects.count(), Payment.objects.count()
    with pytest.raises(expected):
        services.register(event, member=user, actor=user, repair_duplicate=True, **consent(waiver))
    row.refresh_from_db()
    assert unchanged_fields(row) == before and row.host_waiver_version_accepted == "v1"
    assert event.registrations.count() == 1
    assert (AuditLog.objects.count(), Payment.objects.count()) == (audit_count, payment_count)
