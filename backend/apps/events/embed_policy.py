"""The per-space event embed allow-list: read, replace (audited) and the framing decision.

A card is framable only when `events.embed` is on AND the space's `EventEmbedPolicy` is
enabled with at least one exact HTTPS origin; both default off (#95). Writes go through
the settings-authority layer (#101, #128 C-11c): the Space Manager always, the Event
Manager only with the events settings grant and never past a lock.
"""

from django.db import transaction

from apps.audit import services as audit
from apps.makerspaces.capability_eligibility import configuration_feature_enabled
from apps.tenant_migration.gate_runtime import tenant_write

from .models_embed_policy import EventEmbedPolicy

FEATURE = "events.embed"
SETTING_KEY = "event_embed_policy"


def policy_for(space):
    """The stored policy, or the unsaved default (off, no origins)."""
    return EventEmbedPolicy.objects.filter(makerspace=space).first() or EventEmbedPolicy(makerspace=space)


def save_policy(space, *, actor, enabled, allowed_origins):
    from apps.makerspaces.folded_capabilities import require_capability
    from apps.makerspaces.settings_authority import assert_setting_write

    require_capability(space, FEATURE)
    decision = assert_setting_write(actor, space, "events", SETTING_KEY)
    with tenant_write(space.pk), transaction.atomic():
        policy, _ = EventEmbedPolicy.objects.select_for_update().get_or_create(makerspace=space)
        before_enabled, before_origins = policy.enabled, list(policy.allowed_origins)
        policy.enabled, policy.allowed_origins, policy.updated_by = enabled, list(allowed_origins), actor
        policy.save(update_fields=("enabled", "allowed_origins", "updated_by", "updated_at"))
        if (before_enabled, before_origins) != (policy.enabled, policy.allowed_origins):
            audit.record(actor, "event.embed_policy_updated", makerspace=space, target=policy, meta={
                "enabled": policy.enabled, "origin_count": len(policy.allowed_origins),
                "origins_added": sorted(set(policy.allowed_origins) - set(before_origins)),
                "origins_removed": sorted(set(before_origins) - set(policy.allowed_origins)),
                "via": decision.via, "grant_id": decision.grant_id,
            })
        return policy


def framing_origins(space):
    """Exact origins allowed to frame this space's event cards; empty means do not serve."""
    if not configuration_feature_enabled(space, FEATURE):
        return []
    policy = EventEmbedPolicy.objects.filter(makerspace=space, enabled=True).first()
    if policy is None:
        return []
    from rest_framework.exceptions import ValidationError
    from apps.makerspaces.website_origins import validate_origins
    try:
        return validate_origins(list(policy.allowed_origins))
    except ValidationError:
        return []  # A stored value that no longer validates fails closed.
