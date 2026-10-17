"""Core addressed-recipient selection shared with the optional inbox."""
from apps.accounts import rbac
from apps.accounts.models import User
from apps.integrations import recipients as selection
from apps.integrations.staff_notifications import staff_user_ids_for_feature
from apps.makerspaces.models import MakerspaceMembership


def eligible_owner(makerspace, user_id):
    """Account-only owners remain eligible for inbox; messaging adds membership gates."""
    if not user_id or not User.objects.filter(pk=user_id, is_active=True,
        access_status=User.AccessStatus.ACTIVE, is_tenant_dump_stub=False).exists():
        return False
    membership = rbac.scope_notification_policy(MakerspaceMembership.objects.all(),
        makerspace_id=makerspace.pk).filter(user_id=user_id).first()
    return membership is None or (membership.status == "active" and membership.receives_notifications)


def owner_deliveries(payload):
    """Keep the inbox's mail fallback and explicit-summary override order."""
    return [mail for mail in payload.emails if mail.user_id and mail.audience in {"requester", "member"}] + list(payload.inbox)


def addressed_recipients(makerspace, feature, event, payload):
    recipients = {}
    if payload.staff_channels_enabled:
        recipients.update((pk, "staff") for pk in staff_user_ids_for_feature(makerspace, feature, event, payload.scope))
    if not selection.has_selection(makerspace, feature, event, payload.scope) or selection.requester_selected(
        makerspace, feature, event, payload.scope,
    ):
        for own in owner_deliveries(payload):
            if eligible_owner(makerspace, own.user_id):
                recipients[own.user_id] = "member"
    return list(recipients.items())
