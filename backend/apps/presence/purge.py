"""Retention registration survives tombstoning; no private object bytes here."""


def delete(space, cursor):
    from apps.makerspaces.module_purge_collectors_single_model import PurgeResult
    from .models import (
        AnthiasAssetLink, AnthiasPlayer, DisplayScreen, PresenceSession, PresencePreference, PresenceSettings, SpaceNowConfig,
    )
    deleted, counts = 0, {}
    for model in (DisplayScreen, AnthiasPlayer, SpaceNowConfig, PresenceSession, PresencePreference, PresenceSettings):
        count, labels = model.objects.filter(makerspace=space).delete()
        deleted += count
        for label, value in labels.items():
            counts[label] = counts.get(label, 0) + value
    return PurgeResult(counts, {model._meta.label for model in (DisplayScreen, AnthiasPlayer, AnthiasAssetLink, SpaceNowConfig, PresenceSession, PresencePreference, PresenceSettings)})
