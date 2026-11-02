"""Release-2 lane L26 (public stats page, #170): literal export classification.

The Settings › Public stats group adds five plain settings columns to the makerspace: the
ordered section keys, the fixed period, the headline metric keys (both comma-separated key
lists, never references) and the TV mode switch and refresh. They export with the space.
"""

EXTRA_FIELDS = {
    "makerspaces.Makerspace": "public_stats_sections public_stats_period public_stats_headline "
                              "public_stats_tv_mode_enabled public_stats_tv_refresh_seconds",
}


def extend(fields):
    for label, extra in EXTRA_FIELDS.items():
        fields[label] += " " + extra
    return fields
