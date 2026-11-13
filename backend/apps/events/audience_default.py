"""With Membership off, the default `members` audience cannot be registered for (decision 223).

`registration_access.require_registration_access` refuses every `members`-audience
registration while the `membership` module is off, so publishing such an event would
create an event nobody can join. Publish therefore falls back to the `accounts` audience
(any active account) and audits the change. If the space has the account-registration
feature off there is no audience that works, so publish is refused with a clear code.
"""

from django.utils.translation import gettext
from rest_framework.exceptions import ValidationError

from apps.makerspaces.platform import feature_enabled, module_enabled

CODE = "audience_requires_membership"


def needs_fallback(event):
    return event.registration_audience == "members" and not module_enabled(event.makerspace, "membership")


def apply_membership_off_fallback(event):
    """Switch a `members` event to `accounts` when Membership is off. Returns True if changed.

    The caller saves `registration_audience` and audits. Raises when no audience can work.
    """
    if not needs_fallback(event):
        return False
    if not feature_enabled(event.makerspace, "events.account_registration"):
        raise ValidationError({"registration_audience": gettext(
            "Membership is off, so nobody can register for a members-only event. "
            "Turn on account registration for events or choose another audience."),
            "code": CODE})
    event.registration_audience = "accounts"
    return True
