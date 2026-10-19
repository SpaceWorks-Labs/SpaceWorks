"""Profile mutation summaries; authored content and handle strings are never audit metadata."""
from .presentation_catalog_types import P

ENTRIES = (
    P("public_page.unattached_assets_removed", "Unattached public page images removed", ("owner_kind", "count")),
    P("public_page.asset_bytes_deleted", "Public page image storage released", ("owner_kind",)),
    P("public_page.updated", "Public page draft saved"),
    P("public_page.published", "Public page published"),
    P("public_page.unpublished", "Public page unpublished"),
    P("public_page.handle_claimed", "Public page handle claimed"),
    P("public_page.handle_released", "Public page handle released"),
    P("public_page.asset_reserved", "Public page image upload reserved"),
    P("public_page.asset_uploaded", "Public page image uploaded"),
    P("public_page.asset_deleted", "Public page image deleted"),
    P("member.public_handle_claimed", "Public profile handle claimed", ("changed",)),
    P("member.public_handle_released", "Public profile handle released"),
    P("member.profile_timeline_created", "Profile timeline entry added", ("fields",)),
    P("member.profile_timeline_updated", "Profile timeline entry updated", ("fields",)),
    P("member.profile_timeline_deleted", "Profile timeline entry deleted"),
)
