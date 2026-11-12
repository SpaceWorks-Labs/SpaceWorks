"""Shared quote, duplicate lookup and registration receipt writers."""
from django.utils.translation import gettext
from django.conf import settings
from apps.events.models import EventRegistration

def _quote(event, member, ticket, invite_code, promo_code, *, actor, admission_locked=True):
    from decimal import Decimal
    from .invites import redeem_invite
    from .promos import redeem_promo

    from .organization_audience import AUDIENCE
    if admission_locked:
        from . import invites
        from .hackathons.admission_errors import fail
        def required(name):
            callback = getattr(invites, name, None)
            if callback is None:
                fail("programme_dependency_unavailable", gettext("Invitation admission is temporarily unavailable."), status=503)
            return callback
        if event.registration_audience in ("invite", AUDIENCE):
            redeem_invite = required("redeem_invite_locked")
    invite = redeem_invite(event, invite_code, member, actor=actor) if (event.registration_audience == "invite" and invite_code
             or event.registration_audience == AUDIENCE and invite_code) else None
    from apps.makerspaces.platform import feature_enabled
    if event.registration_audience == "invite" and not invite_code:
        from .invites import resolve_for_account
        if admission_locked:
            resolve_for_account = required("resolve_for_account_locked")
        from rest_framework.exceptions import NotFound, ValidationError
        if not member or not member.email_verified_at:
            raise ValidationError({"detail": gettext("Verify your email to use your invitation."), "code": "email_verification_required"})
        invite = resolve_for_account(event, member, actor=actor)
        if invite is None:
            raise NotFound(gettext("Invitation not found."))
    if event.registration_audience == AUDIENCE and not invite_code and feature_enabled(event.makerspace, "events.invites"):
        from .invites import resolve_for_account
        if admission_locked:
            resolve_for_account = required("resolve_for_account_locked")
        invite = resolve_for_account(event, member, actor=actor)
    amount = Decimal(ticket.amount if ticket else event.payment_amount)
    # Lane L15 (A3): the member's one best automatic discount first, then the promo on top.
    from .service_payments import member_price
    amount, member_saving = member_price(event, member, amount, ticket)
    promo, discount = redeem_promo(event, promo_code, amount) if promo_code else (None, Decimal("0"))
    return {"registration_audience": event.registration_audience, "ticket_type": ticket, "invite": invite, "promo_code": promo,
            "quoted_amount": amount - discount, "discount_amount": discount + member_saving}


def _existing_registration(event, member, normalized_email, generation, event_hash):
    if member is not None:
        existing = EventRegistration.objects.select_for_update().filter(
            event=event, member=member
        ).first()
        if existing:
            return existing
    if not settings.PII_ENCRYPTION_ENABLED:
        return EventRegistration.objects.select_for_update().filter(event=event, email=normalized_email).first()
    candidates = EventRegistration.objects.select_for_update().filter(
        event=event, email_hash_generation=generation, email_exact_hash=event_hash
    )
    existing = next((row for row in candidates if row.email.strip().lower() == normalized_email), None)
    if settings.PII_ENCRYPTION_DUAL_READ:
        from apps.encryption.search import legacy_plaintext_candidates

        legacy = legacy_plaintext_candidates(
            EventRegistration.objects.filter(event=event), field_name="email", term=normalized_email, exact=True
        )
        if legacy:
            return EventRegistration.objects.select_for_update().filter(pk__in=legacy).first() or existing
    return existing


def _record_registration(event, actor, registration, status):
    from apps.events import services

    services._audit(
        event,
        actor,
        "event.registration_created",
        registration,
        {"registration_id": registration.pk, "status": status},
    )
    if registration.invite_id:
        services._audit(event, actor, "event.invite_redeemed", registration, {"invite_id": registration.invite_id})
    if registration.promo_code_id:
        services._audit(event, actor, "event.promo_redeemed", registration, {"promo_id": registration.promo_code_id, "discount_amount": str(registration.discount_amount)})
    lifecycle_event = "registration_created"
    if status == EventRegistration.Status.PENDING_APPROVAL:
        services._audit(
            event,
            actor,
            "event.registration_approval_requested",
            registration,
            {"registration_id": registration.pk},
        )
        lifecycle_event = "registration_pending_approval"
    elif status == EventRegistration.Status.WAITLISTED:
        lifecycle_event = "registration_waitlisted"
    services.notify_event_lifecycle(event, lifecycle_event, registration.pk)
    if status == EventRegistration.Status.REGISTERED:
        from apps.events.service_payments import create_for_registered_registration

        create_for_registered_registration(registration, actor)
    return services._refresh(registration)


def require_collaborative_locked(event, member, via):
    from rest_framework.exceptions import NotFound
    from apps.events.models import EventCollaborator
    from apps.makerspaces.models import MakerspaceMembership
    from apps.makerspaces.guards import require_module_locked
    from apps.makerspaces.servability import servable_queryset
    from apps.presence.guard import require_active_member
    if via is None:
        raise NotFound()
    if via.pk != event.makerspace_id and not servable_queryset(EventCollaborator.objects.filter(
            event=event, makerspace=via, status="accepted"), relation="makerspace").exists():
        raise NotFound()
    require_module_locked(via.pk, "events")
    MakerspaceMembership.objects.select_for_update().filter(makerspace=via, user=member).first()
    require_active_member(member, via)
