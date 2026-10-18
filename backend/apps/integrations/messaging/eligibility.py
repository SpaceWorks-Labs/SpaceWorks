"""Read-only ordered policy checks; quota mutation is deliberately separate."""
from django.apps import apps
from django.db import transaction
from django.utils import timezone

from apps.accounts import rbac
from apps.integrations.destinations import NotificationScope
from apps.integrations.models import MessagingDelivery
from apps.integrations.notification_catalog import is_notification_enabled
from apps.integrations.recipients import feature_available, has_selection, requester_selected
from apps.integrations.staff_notifications import staff_user_ids_for_feature
from apps.makerspaces.models import MakerspaceMembership
from apps.makerspaces.platform import module_enabled
from apps.makerspaces.servability import is_servable
from .consent import live_consent
from .protections import recipient_hash, suppressed
from .resolver import resolve_sender
from .sources import current_scope, current_source, owner_matches
from .templates import binding_for
from .ties import has_tenant_tie


def eligibility(candidate_or_delivery):
    """Return 'ok' or the first failed gate, without changing any persistent state."""
    row = candidate_or_delivery
    space, user = row.makerspace, row.user
    if not is_servable(space):
        return "tenant_unservable"
    if not module_enabled(space, row.channel):
        return "module_disabled"
    diagnostic = row.source_type == "messaging_test"
    if not feature_available(space, row.feature):
        return "feature_unavailable"
    if not is_notification_enabled(space, row.feature, row.channel):
        return "matrix_disabled"
    if not user.is_active or user.access_status != "active" or user.is_tenant_dump_stub or user.deletion_requested_at:
        return "account_inactive"
    membership = rbac.scope_notification_policy(MakerspaceMembership.objects.all(),
        makerspace_id=space.pk).filter(user=user, status="active").first()
    if row.audience == "staff" or diagnostic:
        if membership is None:
            return "no_tenant_tie"
    elif not has_tenant_tie(user, space):
        return "no_tenant_tie"
    if membership is not None and not membership.receives_notifications:
        return "membership_opted_out"
    source = current_source(row)
    if source is None or current_scope(row, source) != row.scope:
        return "source_changed"
    scope = NotificationScope.from_dict(row.scope)
    if diagnostic:
        selected = row.source_id == str(user.pk) and rbac.can(user, rbac.Action.MANAGE_MAKERSPACE, space.pk)
    elif row.audience == "staff":
        selected = user.pk in staff_user_ids_for_feature(space, row.feature, row.event, scope)
    else:
        selected = owner_matches(row, source) and (not has_selection(space, row.feature, row.event, scope)
            or requester_selected(space, row.feature, row.event, scope))
    if not selected:
        return "recipient_changed"
    # Never import the optional notifications app unless installed AND enabled.
    if apps.is_installed("apps.notifications") and module_enabled(space, "notifications"):
        from apps.notifications.preferences import personal_enabled
        if not personal_enabled(space, user.pk, row.feature, row.channel, event=row.event):
            return "personal_disabled"
    if not user.phone_e164 or not user.phone_verified_at:
        return "phone_unverified"
    if not live_consent(space, user, row.channel):
        return "no_consent"
    sender = resolve_sender(space, row.channel)
    if sender is None:
        return "sender_unavailable"
    if suppressed(row.channel, sender.sender_key, recipient_hash("phone", user.phone_e164)):
        return "suppressed"
    if row.channel == "whatsapp" and binding_for(space, sender, row.feature, row.event, row.audience) is None:
        return "no_template"
    return "ok"


evaluate = eligibility


@transaction.atomic
def reserve_quota(delivery):
    """Serialize by delivery; retries and duplicate enqueues never spend twice."""
    from apps.makerspaces.limits import reserve_notification_quota
    locked = MessagingDelivery.objects.select_for_update().get(pk=delivery.pk)
    if locked.quota_reserved_at is not None:
        delivery.quota_reserved_at = locked.quota_reserved_at
        return True
    if not reserve_notification_quota(delivery.makerspace, delivery.channel):
        return False
    delivery.quota_reserved_at = timezone.now()
    MessagingDelivery.objects.filter(pk=delivery.pk).update(quota_reserved_at=delivery.quota_reserved_at)
    return True
