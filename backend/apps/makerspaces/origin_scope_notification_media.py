"""Resolve a media grant's tenant without consuming or authorizing the grant."""

import hashlib

from django.apps import apps
from django.utils import timezone


def media_grant_targets(token):
    if not isinstance(token, str) or not token or len(token) > 256:
        return set()
    digest = hashlib.sha256(token.encode("utf-8")).hexdigest()
    model = apps.get_model("integrations.NotificationMediaGrant")
    tenant_id = model.objects.filter(
        token_digest=digest, consumed_at__isnull=True, expires_at__gt=timezone.now(),
    ).values_list("delivery__makerspace_id", flat=True).first()
    return {tenant_id} if tenant_id is not None else set()
