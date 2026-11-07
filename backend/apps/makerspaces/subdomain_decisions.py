"""Decide a platform web-address (subdomain) request: one path for /control/ and the web console (#190).

Approving provisions the label and marks the request approved in one transaction; either
decision is audited and the requester is told (a notification failure never undoes it).
"""

from django.utils.translation import gettext
from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import transaction
from django.utils import timezone

from apps.audit import services as audit
from apps.makerspaces.models import Makerspace, SubdomainRequest
from apps.makerspaces.provisioning import provision_subdomain
from apps.makerspaces.subdomain_notifications import notify_subdomain_request_resolved

FIELDS = ["status", "decided_by", "decided_at", "updated_at"]


def _pending(pk):
    locked = SubdomainRequest.objects.select_for_update().get(pk=pk)
    if locked.status != SubdomainRequest.Status.PENDING:
        raise ValidationError(gettext("This web address request is already decided."))
    return locked


def _decided(locked, actor, status):
    locked.status, locked.decided_by, locked.decided_at = status, actor, timezone.now()
    locked.save(update_fields=FIELDS)


def _notify(row):
    try:
        notify_subdomain_request_resolved(row)
    except Exception:  # noqa: BLE001 - the decision stands even when the email fails
        pass


def approve(actor, subdomain_request):
    with transaction.atomic():
        locked = _pending(subdomain_request.pk)
        space = Makerspace.objects.select_for_update().get(pk=locked.makerspace_id)
        suffix = str(settings.PLATFORM_DOMAIN_SUFFIX or "").strip().lower()
        current = (space.frontend_domain or "").lower()
        if suffix and current and current.endswith(suffix):
            raise ValidationError(gettext("This makerspace already has a platform subdomain."))
        space = provision_subdomain(space, locked.requested_label, actor)
        _decided(locked, actor, SubdomainRequest.Status.APPROVED)
    audit.record(actor, "makerspace.subdomain_request_approved", makerspace=space, target=locked,
                 meta={"frontend_domain": space.frontend_domain})
    _notify(locked)
    return locked


def reject(actor, subdomain_request):
    with transaction.atomic():
        locked = _pending(subdomain_request.pk)
        _decided(locked, actor, SubdomainRequest.Status.REJECTED)
    audit.record(actor, "makerspace.subdomain_request_rejected", makerspace=locked.makerspace, target=locked)
    _notify(locked)
    return locked
