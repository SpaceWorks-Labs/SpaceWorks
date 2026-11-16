"""Native event-role grants (#173): a step-up on a person, limited to one event's programme routes.

A person who holds an ACTIVE event role (judge, mentor, volunteer, crew lead: any live event staff
grant for that event, direct or through its series) may step an existing device session up to an
``event`` grant with the same attestation, app-version and second-factor rules as the staff
step-up. The grant carries NO staff authority (rbac sees no staff rows) and its route gate admits
only that event's programme routes (``native_event_routes``). It lives only as long as the role:

- the event-grant signals re-check the person after any grant or entitlement change commits;
- every device request and refresh re-checks the role (``event_role_state``), so a bulk update
  that fires no signal still cannot leave a usable grant behind.
"""

from django.utils.translation import gettext
import logging

from django.db import transaction

from apps.accounts import audit_events

logger = logging.getLogger(__name__)
ACTIVE, LOST = "active", "lost"


def live_event(event_id):
    """The event, when it can still be worked on natively (published, servable, events on)."""
    from apps.separability.registry import runtime_active
    if not runtime_active("events"):
        return None
    from apps.events.models import Event
    from apps.makerspaces.platform import module_enabled
    from apps.makerspaces.servability import is_servable
    event = Event.objects.select_related("makerspace").filter(pk=event_id).first()
    if event is None or event.status != "published" or not is_servable(event.makerspace):
        return None
    return event if module_enabled(event.makerspace, "events") else None


def event_role_state(user, event_id):
    """``active`` while the person holds a live event staff grant for this event, else ``lost``."""
    from django.db.models import Q
    from apps.events.event_authority import active_grants
    event = live_event(event_id)
    if event is None:
        return LOST
    rows = active_grants(user, makerspace_id=event.makerspace_id).filter(
        Q(event_id=event.pk) | Q(series_id=event.series_id, series__isnull=False))
    return ACTIVE if rows.exists() else LOST


@transaction.atomic
def revoke_event_grants(user, event_id=None, *, reason, actor=None):
    from apps.accounts.models_devices import DeviceGrant
    from apps.accounts.services_tokens import revoke_device_grant

    grants = DeviceGrant.objects.filter(user_id=user.pk, authority=DeviceGrant.Authority.EVENT,
                                        status=DeviceGrant.Status.ACTIVE, revoked_at__isnull=True)
    if event_id is not None:
        grants = grants.filter(event_id=event_id)
    revoked = 0
    for grant in grants.order_by("pk"):
        revoke_device_grant(grant)
        revoked += 1
        audit_events.record_auth_event(actor, "auth.event_grant_revoked", target=user, makerspace=_space(grant),
                                       meta={"grant_hash": audit_events.fingerprint(grant.pk), "reason": reason})
    return revoked


def _space(grant):
    from apps.separability.registry import runtime_active
    if not runtime_active("events"):
        return None
    from apps.events.models import Event
    event = Event.objects.select_related("makerspace").filter(pk=grant.event_id).first()
    return event.makerspace if event else None


def audit_issued(user, grant):
    audit_events.record_auth_event(user, "auth.event_grant_issued", target=user, makerspace=_space(grant),
                                   meta={"grant_hash": audit_events.fingerprint(grant.pk),
                                         "login_method": grant.login_method})


def event_authority_for_login(user, event_id):
    """The event step-up behind a real second factor (same proof as the staff step-up)."""
    from rest_framework.exceptions import AuthenticationFailed
    from apps.accounts.mfa_policy import VERIFIED, source_for
    from apps.accounts.models_devices import DeviceGrant
    if event_role_state(user, event_id) != ACTIVE:
        raise AuthenticationFailed(gettext("An active event role is required for this event."))
    if source_for(user) != VERIFIED:
        raise AuthenticationFailed(gettext("Native event sessions require a verified second factor."))
    return DeviceGrant.Authority.EVENT


def assert_registration_for_event(registration, event_id):
    """A space-locked app registration serves only events of its own space."""
    from rest_framework.exceptions import AuthenticationFailed
    event = live_event(event_id)
    if event is None or registration.makerspace_id not in (None, event.makerspace_id):
        raise AuthenticationFailed(gettext("Device registration is not approved for that event."))


def revoke_if_event_role_lost(user, event_id, *, reason="event_role_ended"):
    state = event_role_state(user, event_id)
    if state == LOST:
        revoke_event_grants(user, event_id, reason=reason)
    return state


def recheck_user(user_id):
    """Re-check every live event grant of one person (after a grant or entitlement change)."""
    from apps.accounts.models import User
    from apps.accounts.models_devices import DeviceGrant
    user = User.objects.filter(pk=user_id).first()
    if user is None:
        return
    for event_id in set(DeviceGrant.objects.filter(user_id=user_id, authority=DeviceGrant.Authority.EVENT,
                                                    status=DeviceGrant.Status.ACTIVE).values_list("event_id", flat=True)):
        revoke_if_event_role_lost(user, event_id)


def _grant_changed(sender, instance, **kwargs):
    if kwargs.get("raw"):
        return
    user_id = getattr(instance, "user_id", None)
    if user_id is None and getattr(instance, "grant_id", None):
        from apps.events.models import EventStaffGrant
        user_id = EventStaffGrant.objects.filter(pk=instance.grant_id).values_list("user_id", flat=True).first()
    if user_id is None:
        return

    def _after_commit():
        try:
            recheck_user(user_id)
        except Exception:  # never fail the role change itself; requests re-check anyway
            logger.exception("Event grant revocation after a role change failed", extra={"user_id": user_id})

    transaction.on_commit(_after_commit)


def connect_signals():
    from django.db.models.signals import post_delete, post_save
    from apps.events.models import EventGrantEntitlement, EventStaffGrant

    for model in (EventStaffGrant, EventGrantEntitlement):
        post_save.connect(_grant_changed, sender=model, dispatch_uid=f"accounts.event_grants.{model.__name__}.saved")
        post_delete.connect(_grant_changed, sender=model, dispatch_uid=f"accounts.event_grants.{model.__name__}.deleted")
