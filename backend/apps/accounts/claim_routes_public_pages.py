"""Safe public projections ignore claim credentials; editors require full sessions."""

from .claim_route_types import AnonymousRead

PUBLIC_PAGE_CLAIM_ROUTES = {
    (name, method): AnonymousRead()
    for name in (
        "public-page-handle", "public-makerspace-page", "public-makerspace-page-asset",
        "public-organization-page", "public-organization-page-asset",
        "public-organization-makerspaces", "public-event-code",
    )
    for method in ("GET", "HEAD", "OPTIONS")
}

EDITOR_SUFFIXES = (
    "editor", "publish", "unpublish", "handle", "handle-availability",
    "assets", "asset", "preview", "revisions",
)
MAKERSPACE_PAGE_EDITORS = frozenset(f"makerspace-public-page-{suffix}" for suffix in EDITOR_SUFFIXES)
ORGANIZATION_PAGE_EDITORS = frozenset(f"organization-public-page-{suffix}" for suffix in EDITOR_SUFFIXES)
