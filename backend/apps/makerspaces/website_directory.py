"""Deployment-local discovery/origin policy, independent of domain lifecycle rules."""

from urllib.parse import urlsplit

from django.conf import settings
from django.http import Http404

from .models import Makerspace
from .servability import servable_queryset


def directory_spaces():
    return servable_queryset(Makerspace.objects.filter(
        public_site_enabled=True, superadmin_access_enabled=True,
        hidden_from_central_directory=False,
    ))


def public_url(space, kind, token):
    if kind == "events":
        from .public_page_access import canonical_origin
        return f"{canonical_origin(space)}/e/{token}"
    if space.frontend_domain and space.frontend_domain_status == Makerspace.DomainStatus.VERIFIED:
        return f"https://{space.frontend_domain}/{kind}/{token}"
    return f"{settings.PUBLIC_APP_BASE_URL.rstrip('/')}/m/{space.slug}/{kind}/{token}"


def sitemap_spaces(request):
    host = request.get_host().split(":")[0].lower()
    custom = servable_queryset(Makerspace.objects.filter(
        frontend_domain=host, frontend_domain_status=Makerspace.DomainStatus.VERIFIED,
        public_site_enabled=True, superadmin_access_enabled=True,
    ))
    if custom.exists():
        return custom
    if host != urlsplit(settings.PUBLIC_APP_BASE_URL).hostname:
        raise Http404
    return directory_spaces()
