"""Account-owned booking channels: membership is optional, consent is not."""

from django.core.exceptions import ValidationError
from django.core.validators import validate_email

from apps.accounts.models import User
from apps.integrations import recipients
from apps.integrations.email_preferences import blocked_reason
from apps.integrations.notification_catalog import is_notification_enabled
from apps.makerspaces.platform import module_enabled
from apps.makerspaces.servability import is_servable
from apps.integrations.recipients_owners import eligible_owner


def notification_account(makerspace, account_id, event):
    """Resolve the owner independently of email availability and preferences."""
    if (not is_servable(makerspace)
            or not module_enabled(makerspace, "bookings")
            or not eligible_owner(makerspace, account_id)):
        return None
    if (recipients.has_selection(makerspace, "bookings", event)
            and not recipients.requester_selected(makerspace, "bookings", event)):
        return None
    return User.objects.filter(pk=account_id).first()


def recipient_account(makerspace, account_id, event):
    """Email-only gates also apply at deferred release and retry."""
    account = notification_account(makerspace, account_id, event)
    if (account is None or not module_enabled(makerspace, "email")
            or not is_notification_enabled(makerspace, "bookings", "email")
            or account.email_verified_at is None or not account.email):
        return None
    try:
        validate_email(account.email)
    except ValidationError:
        return None
    if blocked_reason(makerspace, account.email, user_id=account.pk,
                      feature="bookings", stream="bookings", event=event):
        return None
    return account
