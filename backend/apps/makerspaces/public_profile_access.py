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


def profile_is_public(profile):
    if profile is None:
        return False
    membership = profile.membership
    user = membership.user
    return bool(profile.public_visible and profile.public_consented_at
                and is_person(user) and user.is_active and user.access_status == "active"
                and membership.status == "active" and not user.is_tenant_dump_stub
                and is_servable(membership.makerspace)
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


def resolve_public_profile(handle, request=None):
    current = PublicHandle.objects.select_related(
        "profile__membership__user", "profile__membership__makerspace"
    ).filter(handle__iexact=handle, user__isnull=False, profile__isnull=False).first()
    redirected = False
    if current is None:
        retired = PublicHandleRedirect.objects.filter(handle__iexact=handle,
                                                      expires_at__gt=timezone.now(), user__isnull=False).first()
        if retired:
            current = PublicHandle.objects.select_related(
                "profile__membership__user", "profile__membership__makerspace"
            ).filter(user_id=retired.user_id, profile__isnull=False).first()
            redirected = current is not None
    if current is None or not profile_is_public(current.profile):
        raise NotFound()
    # Invalid model-level FK assignment must never attach another person's name.
    if current.user_id != current.profile.membership.user_id:
        raise NotFound()
    if request and any(pk != current.profile.membership.makerspace_id
                       for pk in _request_tenant_ids(request)):
        raise NotFound()
    return current, redirected
