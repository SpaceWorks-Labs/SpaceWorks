"""Profile mutation summaries; authored content and handle strings are never audit metadata."""
from django.utils.translation import gettext_lazy
from .presentation_catalog_types import P

ENTRIES = (
    P("public_page.unattached_assets_removed", gettext_lazy("Unattached public page images removed"), ("owner_kind", "count")),
    P("public_page.asset_bytes_deleted", gettext_lazy("Public page image storage released"), ("owner_kind",)),
    P("public_page.updated", gettext_lazy("Public page draft saved")),
    P("public_page.published", gettext_lazy("Public page published")),
    P("public_page.unpublished", gettext_lazy("Public page unpublished")),
    P("public_page.handle_claimed", gettext_lazy("Public page handle claimed")),
    P("public_page.handle_released", gettext_lazy("Public page handle released")),
    P("public_page.asset_reserved", gettext_lazy("Public page image upload reserved")),
    P("public_page.asset_uploaded", gettext_lazy("Public page image uploaded")),
    P("public_page.asset_deleted", gettext_lazy("Public page image deleted")),
    P("member.public_handle_claimed", gettext_lazy("Public profile handle claimed"), ("changed",)),
    P("member.public_handle_released", gettext_lazy("Public profile handle released")),
    P("member.profile_timeline_created", gettext_lazy("Profile timeline entry added"), ("fields",)),
    P("member.profile_timeline_updated", gettext_lazy("Profile timeline entry updated"), ("fields",)),
    P("member.profile_timeline_deleted", gettext_lazy("Profile timeline entry deleted")),
)
