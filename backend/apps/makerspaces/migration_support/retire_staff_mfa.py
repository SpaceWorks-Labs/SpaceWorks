"""Retiring ``security.staff_mfa_required`` (release 2, S-A): staff MFA is a platform rule.

Used by makerspaces 0119. Kept outside ``migrations/`` so the audit drift guards see the
literal ``makerspace.capability_retired`` action and its metadata (the same
historical-model writer the fixed-roles migration uses; no live event).
"""

from apps.makerspaces.migration_support.fixed_roles_audit import record

RETIRED_KEY = "security.staff_mfa_required"
MODELS = ("makerspaces.Makerspace", "makerspaces.MakerspaceSecurityLock", "audit.AuditLog", "audit.AuditMacKey")


def retire(apps, schema_editor):
    """Strip the key from every space's features and delete its platform locks; one
    audit row per space that had either."""
    alias = schema_editor.connection.alias
    models = {label: apps.get_model(label) for label in MODELS}
    Makerspace, Lock = models["makerspaces.Makerspace"], models["makerspaces.MakerspaceSecurityLock"]
    locked = set(Lock.objects.using(alias).filter(key=RETIRED_KEY).values_list("makerspace_id", flat=True))
    for space in Makerspace.objects.using(alias).only("pk", "enabled_features").order_by("pk").iterator():
        features = list(space.enabled_features or [])
        was_enabled = RETIRED_KEY in features
        if was_enabled:
            space.enabled_features = [key for key in features if key != RETIRED_KEY]
            space.save(using=alias, update_fields=["enabled_features"])
        if was_enabled or space.pk in locked:
            record(space.pk, "makerspace.capability_retired", "makerspaces.makerspace", space.pk,
                   models=models, alias=alias,
                   meta={"key": RETIRED_KEY, "was_enabled": was_enabled, "lock_removed": space.pk in locked})
    Lock.objects.using(alias).filter(key=RETIRED_KEY).delete()
