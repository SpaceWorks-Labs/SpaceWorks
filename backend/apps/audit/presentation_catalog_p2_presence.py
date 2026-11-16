from django.utils.translation import gettext_noop
from .presentation_catalog_types import P

ENTRIES = (
    P("presence.preference_updated", gettext_noop("Presence display preference changed")),
    P("presence.settings_updated", gettext_noop("Presence display settings changed")),
    P("presence.renewed", gettext_noop("Presence renewed")),
    P("presence.display_claimed", gettext_noop("Space display screen paired"), ("panels", "rotation_seconds")),
    P("presence.display_claim_failed", gettext_noop("Space display pairing code not recognised"), ("failures",)),
    P("presence.display_updated", gettext_noop("Space display screen changed"), ("fields",)),
    P("presence.display_unpaired", gettext_noop("Space display screen unpaired")),
    P("presence.display_provisioned", gettext_noop("Space display screen created with a link"), ("panels",)),
    P("presence.display_link_rotated", gettext_noop("Space display link replaced")),
    P("presence.display_players_changed", gettext_noop("Anthias players for a screen changed"), ("players",)),
    P("presence.anthias_player_added", gettext_noop("Anthias player added"), ("name", "host")),
    P("presence.anthias_player_updated", gettext_noop("Anthias player changed"), ("fields",)),
    P("presence.anthias_player_removed", gettext_noop("Anthias player removed"), ("name",)),
    P("presence.anthias_tested", gettext_noop("Anthias player tested"), ("ok", "error")),
    P("presence.anthias_synced", gettext_noop("Anthias player synced"), ("ok", "error")),
    P("presence.now_config_updated", gettext_noop("Public page display settings changed"), ("fields",)),
    P("presence.expired", gettext_noop("Presence expired"), ("cause",)),
    P("presence.expiry_reminded", gettext_noop("Presence expiry reminder queued")),
    P("presence.expiry_reminder_skipped", gettext_noop("Stale presence reminder skipped")),
)
