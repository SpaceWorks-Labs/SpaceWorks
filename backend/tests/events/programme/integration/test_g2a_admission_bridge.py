"""PostgreSQL integration, no replacement registration/status/capacity writer."""
from decimal import Decimal

import pytest
from django.utils import timezone

from apps.events import services
from apps.events.credentials.models import EventRegistrationCredential
from apps.events.hackathons.admission_errors import ProgrammeError
from apps.events.hackathons.admission_rsvp import rsvp
from apps.events.models import EventRegistration, EventTicketType
from apps.events.promos import create_promo
from apps.payments.models import Payment
from .g2a_support import canonical_world, apply, command

pytestmark = pytest.mark.django_db(transaction=True)


def test_pending_has_canonical_answers_frozen_quote_no_money_and_no_usable_qr(canonical_world):
    w = canonical_world
    w.config.review_mode = "rolling"
    w.config.save(update_fields=["review_mode"])
    ticket = EventTicketType.objects.create(event=w.event, makerspace=w.space, name="Maker", amount=20)
    promo, code = create_promo(w.event, actor=w.manager, amount_off=5)
    app = apply(w, ticket_type_id=ticket.pk, promo_code=code)
    registration = app.registration
    assert app.state == "submitted" and registration.status == "pending_approval"
    assert registration.custom_answers == {"version": 2, "form_id": "application", "form_revision": 1, "answers": []}
    assert registration.quoted_amount == Decimal("15") and registration.promo_code_id == promo.pk
    assert registration.credential_mode == "inert"
    assert not EventRegistrationCredential.objects.filter(registration=registration).exists()
    assert not Payment.objects.filter(subject_type="event_registration", subject_id=registration.pk).exists()
    promo.refresh_from_db()
    assert promo.uses == 1


def test_rsvp_records_debt_and_v2_qr_exactly_once(canonical_world):
    w = canonical_world
    app = apply(w)
    assert app.state == "offered"
    payload = command(app.version, decision="accept")
    rsvp(event_id=w.event.pk, actor=w.owner, data=payload)
    rsvp(event_id=w.event.pk, actor=w.owner, data=payload)
    app.refresh_from_db()
    registration = app.registration
    assert app.state == "confirmed" and registration.status == "registered"
    payment = Payment.objects.get(subject_type="event_registration", subject_id=registration.pk)
    assert payment.amount == Decimal("12") and payment.provider == "unclaimed"
    assert registration.payment_via_makerspace_id == w.space.pk
    assert EventRegistrationCredential.objects.filter(registration=registration, revoked_at=None).count() == 1
    assert registration.credential_mode == "v2"


def test_missing_credential_keys_rolls_back_rsvp_and_debt(canonical_world, settings):
    from apps.events.credentials.errors import CredentialKeyUnavailable
    w = canonical_world
    app = apply(w)
    settings.EVENT_REGISTRATION_CREDENTIAL_KEYS = {}
    with pytest.raises(CredentialKeyUnavailable):
        rsvp(event_id=w.event.pk, actor=w.owner, data=command(app.version, decision="accept"))
    app.refresh_from_db()
    assert app.state == "offered" and app.rsvp_accepted_at is None
    assert app.registration.status == "pending_approval"
    assert not Payment.objects.filter(subject_type="event_registration", subject_id=app.registration_id).exists()


@pytest.mark.parametrize("operation", ["approve_registration", "reject_registration", "promote_registration", "restore_registration"])
def test_legacy_decisions_and_restore_cannot_bypass_application(canonical_world, operation):
    w = canonical_world
    app = apply(w)
    callback = getattr(services, operation, None)
    if callback is None:
        from apps.events.services_registration_tools import restore_registration
        callback = restore_registration
    with pytest.raises(ProgrammeError) as error:
        callback(app.registration, actor=w.manager)
    assert error.value.detail["code"] == "hackathon_admission_required"


def test_ordinary_registration_is_refused_even_with_disabled_capability(canonical_world):
    w = canonical_world
    w.space.enabled_features.remove("events.hackathons")
    w.space.save(update_fields=["enabled_features"])
    with pytest.raises(ProgrammeError):
        services.register(w.event, member=w.owner, actor=w.owner)
    assert not EventRegistration.objects.filter(event=w.event).exists()


def test_cancellation_revokes_qr_preserves_money_and_canonical_mapping(canonical_world):
    w = canonical_world
    app = apply(w)
    rsvp(event_id=w.event.pk, actor=w.owner, data=command(app.version, decision="accept"))
    app.refresh_from_db()
    payment = Payment.objects.get(subject_type="event_registration", subject_id=app.registration_id)
    services.cancel_registration(app.registration, actor=w.manager)
    app.refresh_from_db()
    assert app.state == "withdrawn" and app.registration.status == "cancelled"
    assert not EventRegistrationCredential.objects.filter(registration_id=app.registration_id, revoked_at=None).exists()
    assert Payment.objects.filter(pk=payment.pk).exists()


def test_checkin_and_undo_leave_application_confirmed(canonical_world):
    w = canonical_world
    app = apply(w)
    rsvp(event_id=w.event.pk, actor=w.owner, data=command(app.version, decision="accept"))
    app.refresh_from_db()
    registration = services.mark_attended(app.registration, actor=w.manager)
    assert registration.status == "attended"
    corrected, _ = services.correct_attendance(registration, actor=w.manager)
    app.refresh_from_db()
    assert corrected.status == "registered" and app.state == "confirmed"


def test_invite_path_fails_closed_until_shared_locked_invite_port_lands(canonical_world, monkeypatch):
    from apps.events import invites
    monkeypatch.delattr(invites, "redeem_invite_locked", raising=False)
    monkeypatch.delattr(invites, "resolve_for_account_locked", raising=False)
    w = canonical_world
    w.event.registration_audience = "invite"
    w.event.save(update_fields=["registration_audience"])
    w.owner.email_verified_at = timezone.now()
    w.owner.save(update_fields=["email_verified_at"])
    with pytest.raises(ProgrammeError) as error:
        apply(w, invite_code="not-a-credential")
    assert error.value.detail["code"] == "programme_dependency_unavailable"
    assert not EventRegistration.objects.filter(event=w.event).exists()


def test_missing_contributor_cancellation_hook_rolls_back_entire_event(canonical_world, monkeypatch):
    from apps.events.contributions.errors import ProgrammeError as ContributorError
    from apps.events.contributions.models_roles import EventRoleAssignment
    from apps.events.contributions import role_workflow
    monkeypatch.delattr(role_workflow, "cancel_event_locked", raising=False)
    w = canonical_world
    role = EventRoleAssignment.objects.create(event=w.event, makerspace=w.space, member=w.owner,
                                               role="volunteer", state="applied")
    with pytest.raises(ContributorError) as error:
        services.cancel(w.event, actor=w.manager)
    assert error.value.status_code == 503
    w.event.refresh_from_db()
    role.refresh_from_db()
    assert w.event.status == "published" and role.state == "applied"


def test_schedule_delegate_keeps_exact_existing_field_permissions():
    from datetime import timedelta
    from rest_framework.exceptions import PermissionDenied
    from tests.events.staff_grant_helpers import grant_fixture
    _, _, delegate, event, _ = grant_fixture("publish_schedule")
    updated = services.update_event(event, actor=delegate, starts_at=event.starts_at + timedelta(minutes=1))
    assert updated.event_date_revision == 2
    with pytest.raises(PermissionDenied):
        services.update_event(event, actor=delegate, title="Cannot edit details")
