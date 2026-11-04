"""Release-2 lane L25: tenant-dump field snapshot of the analytics connections.

Both are OMITTED (data_export `classification_r2_l25` gives each reason).
"""

_COMMON = ("id metabase_url embed_secret dashboards login_role login_password login_created_at "
           "login_rotated_at updated_at")

FIELD_NAMES = {
    "analytics.AnalyticsConnection": frozenset(f"{_COMMON} makerspace show_member_details".split()),
    "analytics.PlatformAnalyticsConnection": frozenset(f"{_COMMON} singleton".split()),
}
