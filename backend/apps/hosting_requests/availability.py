"""Hosting requests exist only on a managed deployment.

Self-host (blank ``PLATFORM_DOMAIN_SUFFIX``) has one operator who creates their own
spaces, so the feature is inert there unless the operator sets
``PUBLIC_SPACE_REQUESTS_ENABLED`` (decision 295, default off): routes 404, the config flag
is absent and the /control/ entry is hidden. The public half additionally needs working platform
mail and a public base URL, because every applicant must confirm their address through a
link before a request reaches review.
"""

from django.conf import settings
from django.http import Http404

from apps.integrations.email import email_enabled
from apps.makerspaces import domain_verification


def self_host_requests_enabled() -> bool:
    """Decision 295: a self-hosted operator may open the request form (default OFF)."""
    return bool(getattr(settings, "PUBLIC_SPACE_REQUESTS_ENABLED", False))


def admin_available() -> bool:
    # Managed deployments always review; self-host reviews once the operator opened the form.
    return domain_verification.hosts_other_spaces() or self_host_requests_enabled()


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
