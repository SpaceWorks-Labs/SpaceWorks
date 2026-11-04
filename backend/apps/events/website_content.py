"""Bounded editorial vocabulary shared by storage, copying and projection."""

PAGE_GROUPS = ("HERO", "ABOUT", "HIGHLIGHTS", "SCHEDULE", "SPEAKERS", "SPONSORS",
               "VENUE", "FAQ", "RESOURCES", "EDITORIAL")
SECTION_GROUPS = {"logo": "HERO", "intro": "ABOUT", "highlight": "HIGHLIGHTS",
                  "track": "SCHEDULE", "room": "VENUE", "speaker": "SPEAKERS",
                  "sponsor": "SPONSORS", "faq": "FAQ", "resource": "RESOURCES",
                  "prizes": "SPONSORS", "judges": "SPEAKERS", "mentors": "SPEAKERS",
                  "project_gallery": "HIGHLIGHTS", "results": "HIGHLIGHTS"}
SPONSOR_TIERS = ("platinum", "gold", "silver", "partner", "community_partner")
SECTION_DETAIL_DEFAULTS = dict.fromkeys(
    ("headline", "organization", "website_url", "linkedin_url", "x_url", "icon"), "")
SECTION_DETAIL_DEFAULTS["sponsor_tier"] = "community_partner"
SECTION_DETAIL_DEFAULTS["options"] = {}
PAGE_FIELDS = ("tagline", "accent_color", "section_order", "section_enabled", "venue", "editorial_document")
SECTION_FIELDS = ("kind", "slug", "title", "body", "url", "visibility", "position",
                  "headline", "organization", "website_url", "linkedin_url", "x_url",
                  "sponsor_tier", "icon", "options")


def default_section_order():
    return list(PAGE_GROUPS)


def default_section_enabled():
    return dict.fromkeys(PAGE_GROUPS, True)


def default_editorial_document():
    from apps.makerspaces.public_page_contract import empty_document
    return empty_document("event")


def page_defaults():
    from apps.makerspaces.public_page_contract import empty_document
    return {"tagline": "", "accent_color": "", "section_order": default_section_order(),
            "section_enabled": default_section_enabled(), "venue": None, "editorial_document": empty_document("event")}


def group_enabled(page, group):
    return (group in PAGE_GROUPS and isinstance(page.section_enabled, dict)
            and page.section_enabled.get(group, True) is True)
