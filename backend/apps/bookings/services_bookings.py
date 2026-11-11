'''Audited mutation boundary for bookings and their lifecycle.'''

from django.utils.translation import gettext
from apps.accounts.account_kind_guards import require_member_account

from django.core.exceptions import ValidationError as DjangoValidationError
from django.db import transaction
from django.utils import timezone
from rest_framework import serializers

from apps.audit import services as audit
from apps.accounts.account_obligations import lock_obligation_owner
from apps.bookings import notifications
from apps.bookings.exceptions import BookingConflict, BookingInvalidTransition
from apps.bookings.models import BookableSpace, Booking
from apps.forms_schema.validation import validate_answers
from apps.makerspaces import limits
from apps.makerspaces.guards import require_module_locked
from apps.bookings.services_schedule import confirmed_overlap as _confirmed_overlap


def _locked_space(space_id):
    from apps.tenant_migration.gate_runtime import assert_write_allowed
    candidate = BookableSpace.objects.only("makerspace_id").get(pk=space_id)
    assert_write_allowed(candidate.makerspace_id)
    locked = BookableSpace.objects.select_for_update().get(pk=space_id)
    locked.makerspace = require_module_locked(locked.makerspace_id, "bookings")
    return locked


def _validate(booking):
    for field in ('starts_at', 'ends_at'):
        value = getattr(booking, field)
        if value is not None and timezone.is_naive(value):
            raise serializers.ValidationError({field: gettext('Datetime must include a timezone offset.')})
    try:
        booking.full_clean(validate_unique=False, validate_constraints=False)
    except DjangoValidationError as exc:
        detail = exc.message_dict if hasattr(exc, 'message_dict') else exc.messages
        raise serializers.ValidationError(detail) from exc
    if booking.ends_at <= booking.starts_at:
        raise serializers.ValidationError(
            {'ends_at': gettext('End time must be after start time.')}
        )


def _audit(space, actor, action, target, meta=None):
    return audit.record(
        actor,
        action,
        makerspace=space.makerspace,
        target=target,
        meta=meta or {},
    )


def _require_certification(space, member, actor, override_reason):
    """Gate a member's booking on machine-type training, when the space names a type.

    Imported lazily and skipped entirely unless `machine_type_id` is set, so `bookings`
    never starts requiring the `machines` module: a space with no machine type (every
    space in a bookings-only install) never reaches this import.
    """
    if member is None or not space.machine_type_id:
        return
    from apps.machines.certifications import require_certification_for_member

    require_certification_for_member(
        space.makerspace, member, space.machine_type, purpose='booking',
        actor=actor, override_reason=override_reason,
    )


def _refresh(instance):
    instance.refresh_from_db()
    return instance


@transaction.atomic
def create_booking(
    space, *, starts_at, ends_at, member=None, name=None, email=None, phone=None,
    custom_answers=None, note='', actor=None, certification_override_reason='',
    price_confirmation=None, replaces=None, house=False, organization=None,
):
    """`price_confirmation`: a staff preview digest verified after locked admission
    (`staff_price_confirmation`); a stale one raises 409 before anything is written.
    `replaces`: the locked rejected/cancelled booking this one replaces
    (`services_replacement`); its own debt and history are left untouched.
    `house` (decision 223 (h)): a staff-only booking with no member booker, no charge and no
    plan hours; it needs `manage_reservations` and is confirmed straight away."""
    if house and (member is not None or actor is None or replaces is not None):
        raise serializers.ValidationError({'house': gettext('A house booking has no member and needs a staff actor.')})
    if member is not None:
        require_member_account(member)
    from apps.bookings.admission import admission_status, validate_admission
    from apps.encryption.write_fence import assert_mapped_write_allowed

    assert_mapped_write_allowed(space.makerspace_id)
    locked_space = _locked_space(space.pk)
    member = lock_obligation_owner(member)
    if house:
        from .booking_authority import require
        require(actor, locked_space, "manage_reservations")
    elif actor is not None and getattr(member, "pk", None) != actor.pk:
        from .booking_authority import require
        from apps.presence.guard import require_active_member
        from apps.makerspaces.models import MakerspaceMembership
        require(actor, locked_space, "manage_reservations")
        if member is None or not MakerspaceMembership.objects.filter(
            makerspace_id=locked_space.makerspace_id, user=member, status="active",
        ).exists():
            from rest_framework.exceptions import PermissionDenied
            raise PermissionDenied(gettext("Staff booking requires an active local member."))
        require_active_member(member, locked_space.makerspace)
    now = timezone.now()
    status = Booking.Status.CONFIRMED if house else admission_status(locked_space)
    if house:
        name = (name or '').strip() or gettext('House booking')
        email, phone = actor.email or f'house+{locked_space.makerspace_id}@spaceworks.invalid', ''
    elif member is not None:
        name = member.display_name or member.get_full_name() or member.username
        email = member.email
        phone = member.phone
    booking = Booking(
        space=locked_space,
        member=member,
        name=(name or '').strip(),
        email=(email or '').strip().lower(),
        phone=(phone or '').strip(),
        starts_at=starts_at,
        ends_at=ends_at,
        note=note,
        status=status,
        is_house=house,
    )
    validate_admission(locked_space, booking, now=now, actor=actor,
                       override_reason=certification_override_reason)
    booking.custom_answers = validate_answers(
        locked_space.custom_form, custom_answers
    )
    require_module_locked(locked_space.makerspace, 'bookings')
    limits.check_quota(locked_space.makerspace, 'bookings', adding=1)
    # Decision 221(d): serialise this member's term allowance BEFORE any quote reads it, so the
    # price verified/frozen below is the price the ledger row written after the save matches.
    from apps.bookings import included_hours
    exempt = included_hours.event_venue_exempt(locked_space, member, actor, replaces)
    # Decision 223 (k): an organization's partner-event booking draws nothing from its contact's plan hours.
    exempt = exempt or organization is not None
    included_hours.lock_term(locked_space.makerspace, member, locked_space, starts_at)
    if organization is not None:  # B13: the organization's hours bank is locked before any quote reads it
        from apps.bookings import organization_hours
        organization_hours.lock_bank(locked_space.makerspace, organization)
    verified = None
    if price_confirmation is not None:
        from apps.bookings.staff_price_confirmation import verify
        verified = verify(locked_space, member, starts_at, ends_at, price_confirmation, exempt, organization)
    if status == Booking.Status.PENDING:
        # L15 (#159): approval charges the price quoted now, never a re-quote.
        from apps.bookings.service_payments import requested_snapshot
        booking.pricing_snapshot = requested_snapshot(booking, priced=verified, exempt=exempt, organization=organization)
    booking.replaces = replaces
    booking.save()
    if organization is not None:
        from apps.bookings.organization_booking import link_organization
        link_organization(booking, organization, member, actor)
    _audit(
        locked_space,
        actor,
        'booking.created',
        booking,
        {'booking_id': booking.pk, 'status': status},
    )
    if house:
        _audit(locked_space, actor, 'booking.house_created', booking, {'booking_id': booking.pk})
    else:
        notifications.notify_booking_status(booking, 'created')
    from apps.bookings.included_hours_ledger import consume
    consume(booking, actor=actor, exempt=exempt)  # pending holds its hours too; reject/cancel give them back
    if status == Booking.Status.CONFIRMED:
        from apps.bookings.service_payments import create_for_confirmed_booking

        create_for_confirmed_booking(booking, actor, priced=verified)
    return _refresh(booking)


def _locked_booking(booking):
    from apps.encryption.write_fence import assert_mapped_write_allowed
    assert_mapped_write_allowed(booking.space.makerspace_id)
    space = _locked_space(booking.space_id)
    locked = Booking.objects.select_for_update().get(pk=booking.pk)
    if locked.space_id != space.pk:
        raise BookingInvalidTransition('Booking no longer belongs to this space.')
    return space, locked


@transaction.atomic
def approve_booking(booking, *, actor):
    space, locked = _locked_booking(booking)
    from .booking_authority import require
    require(actor, space, "manage_reservations")
    if locked.status != Booking.Status.PENDING:
        raise BookingInvalidTransition(
            f'Cannot transition booking from {locked.status} to confirmed.'
        )
    if not space.is_active:
        raise BookingInvalidTransition('Inactive spaces cannot approve bookings.')
    from apps.bookings.services_schedule import enforce_opening_hours

    enforce_opening_hours(space, locked.starts_at, locked.ends_at)
    if locked.ends_at <= timezone.now():
        raise BookingInvalidTransition('Ended bookings cannot be approved.')
    if _confirmed_overlap(
        space, locked.starts_at, locked.ends_at, exclude=locked.pk
    ):
        raise BookingConflict('This space is already booked for that time.')
    locked.status = Booking.Status.CONFIRMED
    locked.calendar_sequence += 1
    locked.calendar_updated_at = timezone.now()
    locked.save(update_fields=['status', 'calendar_sequence', 'calendar_updated_at'])
    _audit(
        space,
        actor,
        'booking.approved',
        locked,
        {
            'booking_id': locked.pk,
            'old_status': Booking.Status.PENDING,
            'new_status': Booking.Status.CONFIRMED,
        },
    )
    notifications.notify_booking_status(locked, 'confirmed')
    from apps.bookings.service_payments import create_for_confirmed_booking

    create_for_confirmed_booking(locked, actor, approval=True)
    from .event_link_notices import booking_changed
    booking_changed(locked, 'confirmed')  # decision 223 G4: the event's organizers hear the venue is confirmed
    return _refresh(locked)


@transaction.atomic
def reject_booking(booking, *, actor, reason=""):
    from .services_decisions import clean_reason
    reason = clean_reason(reason, required=True)
    space, locked = _locked_booking(booking)
    from .booking_authority import require
    require(actor, space, "manage_reservations")
    if locked.status != Booking.Status.PENDING:
        raise BookingInvalidTransition(
            f'Cannot transition booking from {locked.status} to rejected.'
        )
    locked.status = Booking.Status.REJECTED
    locked.decision_reason = reason
    locked.calendar_sequence += 1
    locked.calendar_updated_at = timezone.now()
    locked.save(update_fields=['status', 'decision_reason', 'calendar_sequence', 'calendar_updated_at'])
    _audit(
        space,
        actor,
        'booking.rejected',
        locked,
        {
            'booking_id': locked.pk,
            'old_status': Booking.Status.PENDING,
            'new_status': Booking.Status.REJECTED,
            'reason': reason,
        },
    )
    notifications.notify_booking_status(locked, 'rejected')
    from .included_hours_ledger import release
    release(locked, actor)
    from .event_link_notices import booking_changed
    booking_changed(locked, 'rejected')
    return _refresh(locked)


# Explicit compatibility exports; lifecycle policy is kept in its own module.
from apps.bookings.services_transitions import (  # noqa: E402,F401
    cancel_booking, complete_booking, mark_no_show,
)
