"""Live recovery namespaces (a person or the platform superadmin) and trusted destinations."""

from contextlib import contextmanager
from django.conf import settings
from django.core.exceptions import ObjectDoesNotExist
from django.db import transaction
from django.db.models import Q

from apps.accounts.models import User
from apps.accounts.staff_identity import context_label, person_q, platform_q


def recovery_origin(request):
    """Malformed or oversized browser headers never become trusted recovery input."""
    from apps.accounts.social_nonces import request_origin

    try:
        origin = request_origin(request)
    except (TypeError, ValueError):
        return ""
    return origin if len(origin) <= 512 else ""


def lock_recovery_account(account):
    """A concurrently deleted account is an unavailable recovery, never a 500."""
    from apps.accounts.credential_locks import lock_credentials

    if account is None:
        return None
    try:
        return lock_credentials(account)
    except ObjectDoesNotExist:
        return None


@contextmanager
def recovery_transaction(user):
    """Recovery is account-level (a person or the superadmin); no tenant gate is drained."""
    with transaction.atomic():
        yield


def resolve_account(identifier, *, context="member", makerspace=None):
    """``member`` = a person (by email); ``platform`` = the superadmin (username or email).
    The release-1 ``staff`` context resolves nothing."""
    if makerspace or context not in {"member", "platform"}:
        return None
    rows = User.objects.filter(person_q() if context == "member" else platform_q())
    if context == "member":
        return rows.filter(email__iexact=identifier).exclude(email="").first()
    return (rows.filter(username=identifier).first()
            or rows.filter(Q(email__iexact=identifier) & ~Q(email="")).first())


def recoverable(user, *, context, makerspace=None, origin=""):
    if not (user and context_label(user) == context and context in {"member", "platform"}
            and user.is_active and user.retired_at is None and not user.is_tenant_dump_stub
            and getattr(user, "merged_into_id", None) is None
            and user.access_status == User.AccessStatus.ACTIVE
            and not user.is_walk_in and user.email):
        return False
    from apps.accounts.principal_guards import is_anonymous_requester
    if is_anonymous_requester(user):
        return False
    if context == "member":
        return not (user.is_superuser or user.role == User.Role.SUPERADMIN)
    if not isinstance(origin, str) or len(origin) > 512:
        return False
    return origin in settings.PLATFORM_STAFF_ORIGINS


def mail_available(context):
    from apps.integrations.email import email_enabled, platform_email_configured
    return email_enabled() if context == "member" else platform_email_configured()


def reset_destination(user):
    """Where the platform superadmin's emailed recovery points (people use the member flow)."""
    base = (settings.PUBLIC_APP_BASE_URL or "").rstrip("/")
    return f"{base}/admin/reset-password?context=platform", "platform administration"
