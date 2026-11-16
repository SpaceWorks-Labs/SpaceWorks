"""Decide a Space Manager's API key request: one path for /control/ and the web console (#190).

Approving issues a server client inside the space's quota (its secret is returned ONCE to
the caller to show), syncs the space's allowed origins, and audits both the decision and
the new client; rejecting closes the request. The requester is told either way.
"""

from django.utils.translation import gettext
from django.core.exceptions import ValidationError
from django.db import transaction
from django.utils import timezone

from apps.apiclients.models import ApiClient, ApiKeyRequest
from apps.apiclients.notifications import notify_api_key_request_resolved
from apps.apiclients.scope_registry import LEGACY_SCOPE
from apps.apiclients.services import sync_makerspace_origins
from apps.audit import services as audit
from apps.makerspaces import limits

FIELDS = ["status", "resolved_by", "resolved_at", "updated_at"]


def _pending(pk):
    locked = (ApiKeyRequest.objects.select_for_update(of=("self",)).select_related("makerspace", "requester")
              .get(pk=pk))
    if locked.status != ApiKeyRequest.Status.PENDING:
        raise ValidationError(gettext("This API key request is already decided."))
    return locked


def _resolve(locked, actor, status):
    locked.status, locked.resolved_by, locked.resolved_at = status, actor, timezone.now()
    locked.save(update_fields=FIELDS)


def approve(actor, key_request):
    """Returns ``(request, client, raw_secret)``; quota and validation errors propagate."""
    with transaction.atomic():
        locked = _pending(key_request.pk)
        limits.check_quota(locked.makerspace, "api_clients", adding=1)
        client, raw_secret = ApiClient.issue(
            label=locked.label, makerspace=locked.makerspace, allowed_origins=locked.allowed_origins or [],
            created_by=actor, client_type="server", scopes=[LEGACY_SCOPE],
        )
        sync_makerspace_origins(locked.makerspace)
        _resolve(locked, actor, ApiKeyRequest.Status.APPROVED)
        audit.record(actor, "api_key_request.approved", makerspace=locked.makerspace, target=locked,
                     meta={"api_client_id": client.pk})
        audit.record(actor, "api_client.created", makerspace=client.makerspace, target=client,
                     meta={"allowed_origins": client.allowed_origins, "api_key_request_id": locked.pk})
    notify_api_key_request_resolved(locked)
    return locked, client, raw_secret


def reject(actor, key_request):
    with transaction.atomic():
        locked = _pending(key_request.pk)
        _resolve(locked, actor, ApiKeyRequest.Status.REJECTED)
        audit.record(actor, "api_key_request.rejected", makerspace=locked.makerspace, target=locked)
    notify_api_key_request_resolved(locked)
    return locked
