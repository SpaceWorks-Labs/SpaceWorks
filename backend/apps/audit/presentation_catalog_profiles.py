"""Profile mutation summaries; authored content and handle strings are never audit metadata."""
from django.utils.translation import gettext_noop
from .presentation_catalog_types import P

ENTRIES = (
    P("public_page.unattached_assets_removed", gettext_noop("Unattached public page images removed"), ("owner_kind", "count")),
    P("public_page.asset_bytes_deleted", gettext_noop("Public page image storage released"), ("owner_kind",)),
    P("public_page.updated", gettext_noop("Public page draft saved")),
    P("public_page.published", gettext_noop("Public page published")),
    P("public_page.unpublished", gettext_noop("Public page unpublished")),
    P("public_page.handle_claimed", gettext_noop("Public page handle claimed")),
    P("public_page.handle_released", gettext_noop("Public page handle released")),
    P("public_page.asset_reserved", gettext_noop("Public page image upload reserved")),
    P("public_page.asset_uploaded", gettext_noop("Public page image uploaded")),
    P("public_page.asset_deleted", gettext_noop("Public page image deleted")),
    P("member.public_handle_claimed", gettext_noop("Public profile handle claimed"), ("changed", "default")),
    P("member.public_handle_released", gettext_noop("Public profile handle released")),
    P("member.profile_timeline_created", gettext_noop("Profile timeline entry added"), ("fields",)),
    P("member.profile_timeline_updated", gettext_noop("Profile timeline entry updated"), ("fields",)),
    P("member.profile_timeline_deleted", gettext_noop("Profile timeline entry deleted")),
    P("member.profile_achievement_created", gettext_noop("Self-reported achievement added"), ("fields",)),
    P("member.profile_achievement_updated", gettext_noop("Self-reported achievement updated"), ("fields",)),
    P("member.profile_achievement_deleted", gettext_noop("Self-reported achievement deleted")),
    P("member.profile_project_imported", gettext_noop("Hackathon submission imported as a project")),
    P("member.profile_opened", gettext_noop("Member profile created (open by default)")),
)
