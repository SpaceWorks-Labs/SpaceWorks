"""Change the signed-in account's own language preference (phase 8 i18n)."""

from django.db import transaction

from apps.audit import services as audit
from apps.accounts.models import User


def set_preferred_locale(user, code):
    """Store ``code`` (or None) on ``user`` alone; audit only a real change.

    An idempotent same-value write returns without touching the row or the audit log.
    The audit meta carries the two locale codes and nothing else.
    """
    with transaction.atomic():
        locked = User.objects.select_for_update().get(pk=user.pk)
        before = locked.preferred_locale
        if before == code:
            return False
        locked.preferred_locale = code
        locked.save(update_fields=["preferred_locale"])
        user.preferred_locale = code
        audit.record(
            user, "account.locale_changed", target=user,
            meta={"before": before or "default", "after": code or "default"},
        )
    return True
