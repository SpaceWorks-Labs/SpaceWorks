"""One public authorization predicate; every refusal is the same 404."""


from apps.accounts.staff_identity import is_person
from urllib.parse import urlsplit
from django.conf import settings
from django.utils import timezone
from rest_framework.exceptions import NotFound

from .models import Makerspace
from .models_profiles import PublicHandle, PublicHandleRedirect
from .platform import module_enabled
from .servability import is_servable
from .hosting import canonical_host, is_infra_host


def account_is_open_web(user, *, has_handle=None):
    """The OPEN-WEB audience (logged out, decisions 303b/303c): visible, consented, listable, with a handle.

    ``has_handle`` lets a caller that already loaded the handles (one query for a whole team section)
    skip the per-row existence query.
    """
    from .account_profile_read import account_is_listable
    from .models_account_profile import AccountProfile

    account = AccountProfile.objects.filter(user=user).first()
    return bool(account and account.is_visible and account.public_visible and account.public_consented_at
                and account_is_listable(user)
                and (has_handle if has_handle is not None else PublicHandle.objects.filter(user_id=user.pk).exists()))


def profile_is_public(profile, *, has_handle=None):
    """Is this per-space profile REFERENCE publicly showable? (decisions 304/305)

    Stored references (page team members, event website revisions, event profile photos, certificate
    print sources) still name a legacy `MemberProfile` row, but it is only an identity token for
    "this person in this space": the visibility truth is the person's ACCOUNT profile, so a new
    account with no content on the legacy row shows exactly like an old one, and a hidden account
    profile stays hidden everywhere. The reference is also space-scoped, so the membership must still
    be active in a servable space with the membership module on.
    """
    if profile is None:
        return False
    membership = profile.membership
    return bool(account_is_open_web(membership.user, has_handle=has_handle)
                and membership.status == "active" and is_servable(membership.makerspace)
                and module_enabled(membership.makerspace, "membership"))


def _request_tenant_ids(request):
    """Both page origin AND request host constrain reads; neither can widen the other.

    A tenant whose domain became unverified is denied, rather than treated as the
    global platform. Unknown browser origins fail closed too.
    """
    scopes = []
    raw_host = request.get_host()
    hosts = [canonical_host(raw_host) or (raw_host if is_infra_host(raw_host) else None)]
    origin = request.headers.get("Origin") or request.headers.get("Referer")
    if origin:
        try:
            raw_host = urlsplit(origin).netloc
            hosts.append(canonical_host(raw_host) or (raw_host if is_infra_host(raw_host) else None))
        except ValueError:
            raise NotFound()
    platform_hosts = {canonical_host(urlsplit(value).netloc) for value in
                      (*getattr(settings, "PLATFORM_STAFF_ORIGINS", ()), getattr(settings, "PUBLIC_APP_BASE_URL", ""))}
    for host in hosts:
        if not host:
            raise NotFound()
        tenants = list(Makerspace.objects.filter(frontend_domain__iexact=host))
        if tenants:
            if len(tenants) != 1 or tenants[0].frontend_domain_status != Makerspace.DomainStatus.VERIFIED:
                raise NotFound()
            scopes.append(tenants[0].pk)
        elif not is_infra_host(host) and host not in platform_hosts:
            raise NotFound()
    return scopes


def resolve_public_profile(handle, request=None, viewer=None):
    """`(claim, redirected)`; every refusal is the same 404.

    `viewer=None` is the logged-out open-web audience (crawlers, share cards). A signed-in viewer
    passes the real user so non-open-web profiles resolve platform-wide (decision 303a).
    """
    from django.contrib.auth.models import AnonymousUser

    from .account_profile_access import resolve_by_handle

    profile, redirected = resolve_by_handle(handle, viewer if viewer is not None else AnonymousUser(), request)
    return PublicHandle.objects.select_related("user").get(user_id=profile.user_id), bool(redirected)
