"""Hosting requests exist only on a managed deployment.

Self-host (blank ``PLATFORM_DOMAIN_SUFFIX``) has one operator who creates their own
makerspaces, so the whole feature is inert there: routes 404, the config flag is absent
and the /control/ entry is hidden. The public half additionally needs working platform
mail and a public base URL, because every applicant must confirm their address through a
link before a request reaches review.
"""

from django.conf import settings
from django.http import Http404

from apps.integrations.email import email_enabled
from apps.makerspaces import domain_verification


def admin_available() -> bool:
    return not domain_verification.is_self_host()


def public_available() -> bool:
    return (
        admin_available()
        and email_enabled()
        and bool(str(settings.PUBLIC_APP_BASE_URL or "").strip())
    )


def require_public_available():
    if not public_available():
        raise Http404()


def public_base_url() -> str:
    return str(settings.PUBLIC_APP_BASE_URL or "").strip().rstrip("/")
