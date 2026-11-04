"""Retention registration survives tombstoning; no private object bytes here."""


def delete(space, cursor):
    from apps.makerspaces.module_purge_collectors_single_model import PurgeResult
    from .models import PresenceSession, PresencePreference, PresenceSettings
    deleted, counts = 0, {}
    for model in (PresenceSession, PresencePreference, PresenceSettings):
        count, labels = model.objects.filter(makerspace=space).delete()
        deleted += count
        for label, value in labels.items():
            counts[label] = counts.get(label, 0) + value
    return PurgeResult(counts, {model._meta.label for model in (PresenceSession, PresencePreference, PresenceSettings)})
