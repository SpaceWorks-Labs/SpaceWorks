"""Core addressed-recipient selection shared with the optional inbox."""
from apps.integrations import recipients as selection
from apps.integrations.recipients_owners import eligible_owner
from apps.integrations.staff_notifications import staff_user_ids_for_feature


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
