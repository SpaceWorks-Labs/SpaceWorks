"""Exact HTTP/service dispositions for public-page writers (not inferred tenants)."""

from apps.accounts.claim_routes_public_pages import MAKERSPACE_PAGE_EDITORS, ORGANIZATION_PAGE_EDITORS

TENANT_PAGE_ROUTES = MAKERSPACE_PAGE_EDITORS
GLOBAL_PAGE_ROUTES = ORGANIZATION_PAGE_EDITORS
PAGE_SERVICE_PARTICIPANTS = {
    "apps.makerspaces.public_page_services.lock_state": (
        "Typed adapter locks the local Space Manager behind assert_write_allowed, or the global organization governor."
    ),
    "apps.makerspaces.public_page_assets.upload": (
        "Separate durable reservation and finalization repeat lock_state and the tenant fence before committing; global quota uses the organization lock."
    ),
    "apps.makerspaces.public_page_asset_cleanup.collect_unattached": (
        "Tenant cleanup asserts its gate; organization cleanup locks global ownership."
    ),
    "apps.makerspaces.public_page_asset_cleanup.clean_object": (
        "Live tenant bytes repeat their fence; deleted-owner exact-key intents remain deployment cleanup coordination."
    ),
    "apps.makerspaces.public_page_lifecycle.enqueue_tenant_pages": (
        "Only audited whole-tenant/module purge calls this collector inside its authorized deletion transaction."
    ),
}
