"""Live recovery namespaces and trusted destinations, independent of member login policy."""

from contextlib import contextmanager
from django.conf import settings
from django.core.exceptions import ObjectDoesNotExist
from django.db import transaction
from django.db.models import Q

from apps.accounts.models import User
from apps.makerspaces.models import Makerspace, MakerspaceMembership


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
    """Drain with migration writers before taking tenant/account row locks."""
    with transaction.atomic():
        if user and user.staff_makerspace_id:
            from apps.tenant_migration.gate_locks import acquire_shared
            acquire_shared(user.staff_makerspace_id)
        yield


def resolve_account(identifier, *, context="member", makerspace=None):
    rows = User.objects.filter(account_kind=context)
    if context == "staff":
        rows = rows.filter(staff_makerspace__slug=makerspace)
    elif context not in {"member", "platform"} or makerspace:
        return None
    if context == "member":
        return rows.filter(email__iexact=identifier).first()
    return (rows.filter(username=identifier).first()
            or rows.filter(Q(email__iexact=identifier) & ~Q(email="")).first())


def recoverable(user, *, context, makerspace=None, origin=""):
    if not (user and user.account_kind == context and user.is_active
            and user.retired_at is None and not user.is_tenant_dump_stub
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
    if context == "platform":
        return origin in settings.PLATFORM_STAFF_ORIGINS
    if context != "staff" or not user.staff_makerspace_id:
        return False
    from apps.accounts import rbac
    if user.staff_makerspace_id not in rbac.resolve_scope(user):
        return False
    space = Makerspace.objects.filter(pk=user.staff_makerspace_id, slug=makerspace).first()
    if space is None:
        return False
    from apps.makerspaces.servability import is_servable
    from apps.tenant_migration.models_source_gate import SourceMigrationGate
    from apps.makerspaces.platform import makerspace_staff_origins
    # A verified tenant origin or a configured central staff origin must agree with
    # the explicit slug. An arbitrary browser Origin never becomes a recovery door.
    if not is_servable(space) or origin not in makerspace_staff_origins(space):
        return False
    if SourceMigrationGate.objects.filter(makerspace_id=space.pk).exclude(state="open").exists():
        return False
    return MakerspaceMembership.objects.filter(
        user=user, makerspace=space, status="active",
    ).exists()


def mail_available(context):
    from apps.integrations.email import email_enabled, platform_email_configured
    return email_enabled() if context == "member" else platform_email_configured()


def reset_destination(user):
    base = (settings.PUBLIC_APP_BASE_URL or "").rstrip("/")
    if user.account_kind == "platform":
        return f"{base}/admin/reset-password?context=platform", "platform administration"
    space = user.staff_makerspace
    if space.frontend_domain and space.frontend_domain_status == Makerspace.DomainStatus.VERIFIED:
        return f"https://{space.frontend_domain}/admin/reset-password", space.name
    return f"{base}/m/{space.slug}/admin/reset-password", space.name
