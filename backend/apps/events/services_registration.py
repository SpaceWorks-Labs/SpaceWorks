"""Registration mutation boundary, kept separate from event lifecycle services."""

from apps.accounts.account_kind_guards import require_member_account

from django.conf import settings
from django.utils import timezone
from rest_framework.exceptions import ValidationError
from apps.accounts.account_obligations import lock_obligation_owner

from apps.encryption.write_fence import assert_mapped_write_allowed
from apps.events.capacity import (
    effective_registration_cutoff,
    fresh_registration_status,
    registration_is_open,
)
from apps.events.exceptions import (
    DuplicateRegistration,
    EventInvalidTransition,
    RegistrationClosed,
    RegistrationRejected,
)
from apps.events.models import EventRegistration
from apps.forms_schema.validation import validate_answers
from apps.makerspaces.guards import require_module_locked
from apps.events.services_calendar import calendar_registration_changed
from .services_write_boundary import event_write
from .services_registration_preparation import ordinary_form
from .services_registration_preparation import canonical_answers, attach_answers
from .inline_forms import bind_registration_locked, registration_inline


@ordinary_form
@registration_inline
@event_write
def register(
    event, *, member=None, name=None, email=None, phone=None,
    custom_answers=None, actor=None, staff_registration=False,
    via_makerspace=None, collaborative=False,
    invite_code=None, ticket_type_id=None, promo_code=None,
    host_waiver_id=None, host_waiver_version=None, host_waiver_accepted=False, repair_duplicate=False, form_payload=None,
    inline_forms=None,
):
    """Register someone for an event.

    `staff_registration` and `collaborative` each relax exactly one condition: the
    `is_public` requirement. That flag answers "does this event appear in the public
    catalogue", while staff at the door and members of accepted collaborators are not
    the public. Every other rule (published, not ended, capacity, duplicates, the
    custom form, the write fence, and payment) is identical, because this is the same
    service and the state machine has one home.

    An authenticated owner's live-row retry may renew consent after signup closes,
    until the published event ends. It preserves the saved answers and admission state.

    `collaborative=True` is a trusted internal capability restricted to the enforcing
    member view. That view proves an accepted EventCollaborator exists; this service
    deliberately does not re-derive the actor's makerspace membership.
    """
    if member is not None:
        require_member_account(member)
    from apps.events.services import _audit, _locked_event, _refresh, _validate
    from apps.tenant_migration.gate_runtime import assert_write_allowed

    assert_write_allowed(event.makerspace_id)
    assert_mapped_write_allowed(event.makerspace_id)
    locked = _locked_event(event.pk, lock_makerspace=False)
    if staff_registration:
        from .event_authority import require
        require(actor, locked, "manage_registrations")
    from .hackathons.admission_bridge import require_ordinary_registration
    require_ordinary_registration(locked)
    from .organization_audience import AUDIENCE
    from .programme_locks import lock_admission_sources
    lock_admission_sources(locked, [getattr(member, "pk", None)],
                           extra_space_ids=[via_makerspace.pk] if via_makerspace else [])
    if member is not None and locked.registration_audience == AUDIENCE:
        from apps.accounts.models import User
        member = User.objects.filter(pk=member.pk).first()
        from .organization_audience import require_organization_audience
        require_organization_audience(locked, member)
    if member is not None:
        name = member.display_name or member.get_full_name() or member.username
        # Account first, caller's value as the fallback -- the same rule as `phone` just
        # below, and for the same reason: a walk-in record may carry neither, and the
        # registration model requires both.
        email = member.email or email
        # The account wins, but a caller-supplied number is kept as the fallback: a
        # registration needs a contact number (`EventRegistration.phone` is non-blank),
        # and an account without one would otherwise be a dead end nobody at the desk
        # could resolve. The public path passes none, so it is unchanged.
        phone = member.phone or phone
    name = (name or "").strip()
    normalized_email = (email or "").strip().lower()
    phone = (phone or "").strip()
    generation = event_hash = None
    if settings.PII_ENCRYPTION_ENABLED:
        from apps.encryption.blind_index import active_generation, event_email_hash

        generation = active_generation()
        event_hash = event_email_hash(
            normalized_email, generation=generation.generation,
            makerspace_id=event.makerspace_id, event_id=event.pk,
        )
    # register() previously lacked this locked module check. Keep event-then-makerspace
    # ordering: publish() takes the event lock first, so taking the makerspace first
    # here would create a deadlock pair with it.
    locked.makerspace = require_module_locked(locked.makerspace, "events")
    member = lock_obligation_owner(member)
    if collaborative:
        from .services_registration_helpers import require_collaborative_locked
        require_collaborative_locked(locked, member, via_makerspace)
    now = timezone.now()
    if not locked.is_public and not staff_registration and not collaborative:
        raise EventInvalidTransition("This event is not open for registration.")
    existing = _existing_registration(
        locked, member, normalized_email, generation, event_hash
    )
    # Consent repair changes only an owned live row, never admission or queue state.
    # Keep terminal events and cancelled/rejected rows behind normal signup rules.
    consent_repair = bool(
        repair_duplicate and not staff_registration and member and actor
        and actor.is_authenticated and actor.pk == member.pk and existing
        and existing.member_id == member.pk
        and existing.status in (
            EventRegistration.Status.REGISTERED, EventRegistration.Status.WAITLISTED,
            EventRegistration.Status.PENDING_APPROVAL,
        )
        and locked.status == locked.Status.PUBLISHED and now < locked.ends_at
    )
    if not registration_is_open(locked, now) and not consent_repair:
        cutoff = effective_registration_cutoff(locked)
        if (
            locked.status == locked.Status.PUBLISHED
            and now < locked.ends_at
            and cutoff is not None
            and now >= cutoff
        ):
            raise RegistrationClosed("Registration for this event is closed.")
        raise EventInvalidTransition("This event is not open for registration.")
    from .registration_access import require_registration_access
    from .ticketing import select_ticket
    require_registration_access(locked, member, staff=staff_registration, collaborative=collaborative, via=via_makerspace)
    from .host_waivers import require_host_waiver, stamp_host_waiver
    waiver = None
    if locked.registration_audience == AUDIENCE or collaborative:
        waiver = require_host_waiver(
            locked, member, actor=actor, registration=existing,
            host_waiver_id=host_waiver_id, host_waiver_version=host_waiver_version,
            host_waiver_accepted=host_waiver_accepted, allow_consent=not staff_registration,
        )
    # A contact fallback is not proof of ownership. In particular an account with
    # no email must not claim another attendee's cancelled row by naming its email.
    if member is not None and existing and existing.member_id != member.pk:
        raise ValidationError({"email": "This contact cannot be used for this registration."})
    if existing and existing.status != EventRegistration.Status.CANCELLED:
        if existing.status == EventRegistration.Status.REJECTED:
            raise RegistrationRejected("This registration application was rejected.")
        if repair_duplicate:
            stamp_host_waiver(existing, waiver, actor=actor, via=via_makerspace or locked.makerspace, event=locked)
            return existing
        raise DuplicateRegistration("A registration already exists for this email.", fresh_status=existing.status)
    custom_answers = canonical_answers(locked, custom_answers)
    ticket = select_ticket(locked, ticket_type_id, member)
    from .services_registration_admission import require_participant_ticket
    require_participant_ticket(locked, ticket)
    status = fresh_registration_status(locked, ticket)
    if existing and existing.status == EventRegistration.Status.CANCELLED:
        if member is None:
            existing.member = lock_obligation_owner(existing.member)
        # The unique payment subject preserves historical money. Reusing a cancelled
        # paid row would find its terminal charge and silently provide a free place.
        from apps.payments.models import Payment

        if locked.payment_amount > 0 or (ticket and ticket.amount > 0) or (existing.quoted_amount and existing.quoted_amount > 0) or Payment.objects.filter(
            makerspace=locked.makerspace,
            subject_type=Payment.SubjectType.EVENT_REGISTRATION,
            subject_id=existing.pk,
        ).exists():
            raise EventInvalidTransition(
                "A cancelled paid registration cannot be registered again. Contact staff."
            )
        quote = _quote(locked, member, ticket, invite_code, promo_code, actor=actor)
        for field, value in quote.items():
            setattr(existing, field, value)
        existing.member = member or existing.member
        existing.registered_via_makerspace = via_makerspace or locked.makerspace
        # Written together, but they diverge later: a purge clears the provenance above and
        # leaves this one, so a charge raised after that purge still reaches the member.
        existing.payment_via_makerspace = via_makerspace or locked.makerspace
        existing.name, existing.email, existing.phone = name, normalized_email, phone
        existing.custom_answers, existing.status, existing.created_at = custom_answers, status, timezone.now()
        existing.cancelled_at, existing.status_before_cancel, existing.waitlist_position_at = None, "", None
        existing.version += 1
        _validate(existing)
        existing.save(update_fields=[
            "member", "registered_via_makerspace", "payment_via_makerspace", "name",
            "email", "phone", "custom_answers", "status", "created_at", *quote,
            "cancelled_at", "status_before_cancel", "waitlist_position_at", "version",
        ])
        stamp_host_waiver(existing, waiver, actor=actor, via=via_makerspace or locked.makerspace, event=locked)
        attach_answers(locked, existing)
        calendar_registration_changed(existing)
        bind_registration_locked(locked, existing)
        return _record_registration(locked, actor, existing, status)
    quote = _quote(locked, member, ticket, invite_code, promo_code, actor=actor)
    from .credentials.preparation import new_registration_id
    registration = EventRegistration(
        pk=new_registration_id(locked.pk), **quote,
        event=locked, member=member, name=name, email=normalized_email,
        phone=phone, custom_answers=custom_answers, status=status,
        registered_via_makerspace=via_makerspace or locked.makerspace,
        payment_via_makerspace=via_makerspace or locked.makerspace,
    )
    _validate(registration)
    registration.save()
    attach_answers(locked, registration)
    stamp_host_waiver(registration, waiver, actor=actor, via=via_makerspace or locked.makerspace, event=locked)
    bind_registration_locked(locked, registration)
    return _record_registration(locked, actor, registration, status)


from .services_registration_helpers import _quote, _existing_registration, _record_registration
