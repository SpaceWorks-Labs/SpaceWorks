"""Profile mutation summaries; authored content and handle strings are never audit metadata."""
from .presentation_catalog_types import P

ENTRIES = (
    P("member.public_handle_claimed", "Public profile handle claimed", ("changed",)),
    P("member.public_handle_released", "Public profile handle released"),
    P("member.profile_timeline_created", "Profile timeline entry added", ("fields",)),
    P("member.profile_timeline_updated", "Profile timeline entry updated", ("fields",)),
    P("member.profile_timeline_deleted", "Profile timeline entry deleted"),
)
