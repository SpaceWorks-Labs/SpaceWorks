"""The public page's membership-plan cards section (X5), a live derived section.

Shows the space's listed plans (public, active, not archived) with prices and join mode,
only while `membership` and `membership.public_plans` are on; otherwise the section is
left out of the page, like every other derived section whose source is off.
"""


def plan_cards(owner, title):
    from apps.makerspaces.membership_features import membership_feature_on
    from apps.makerspaces.membership_plan_policy import listed_plans
    from apps.makerspaces.views_public_plans import _render
    if not membership_feature_on(owner, "public_plans"):
        return None
    plans = list(listed_plans(owner)[:24])
    if not plans:
        return None
    return {"title": title, "count": len(plans), "results": _render(owner, plans),
            "collection_url": f"/api/v1/public/{owner.slug}/membership-plans"}
