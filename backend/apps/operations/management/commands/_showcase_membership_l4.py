"""Showcase data for the release-2 membership lifecycle (lane L4, LANE-RULES §19).

Turns the 14 `membership.*` switches on in Tinkerspace and seeds what each one needs to
demo: a public financial-year plan and a lifetime plan, a member-number pattern, two
titles (one printed on a card), and a consent purpose. Everything goes through the same
services staff use, so the audit trail is real.
"""
from decimal import Decimal

from apps.makerspaces.membership_admission_settings import update_settings
from apps.makerspaces.models import MakerspaceMembership, MembershipPlan

L4_FEATURES = [f"membership.{key}" for key in (
    "plan_rules", "public_plans", "renewal_desk", "import", "admission_tools", "member_numbers", "records",
    "titles", "consent", "erasure", "history", "register_tools", "insights", "monthly_summary")]


def seed_membership_lifecycle(space, manager, members):
    space.refresh_from_db()
    space.enabled_modules = sorted(set(space.enabled_modules or []) | {"reports"})
    space.enabled_features = sorted(set(space.enabled_features or []) | set(L4_FEATURES))
    space.save(update_fields=["enabled_modules", "enabled_features"])
    MembershipPlan.objects.get_or_create(makerspace=space, name="Annual (financial year)", defaults={
        "interval": "yearly", "amount": Decimal("240.00"), "renewal_amount": Decimal("200.00"), "currency": "usd",
        "plan_type": "financial_year", "slug": "annual", "is_public": True, "sort_order": 1,
        "description": "Runs to the end of the financial year; renewals cost less."})
    MembershipPlan.objects.get_or_create(makerspace=space, name="Lifetime", defaults={
        "interval": "yearly", "amount": Decimal("1500.00"), "currency": "usd", "plan_type": "lifetime",
        "slug": "lifetime", "is_public": True, "sort_order": 2, "auto_renew": False})
    update_settings(manager, space, {
        "member_number_pattern": "TNK-{number:4}", "privacy_notice_version": "2026-10",
        "consent_purposes": [{"key": "photos", "label": "Photos at events",
                              "description": "We may share photos from open days."}]})
    from apps.makerspaces import membership_titles
    treasurer = membership_titles.save_title(manager, space, {"name": "Treasurer", "colour": "citron"})
    membership_titles.save_title(manager, space, {"name": "Mentor", "colour": "sky_blue"})
    first = MakerspaceMembership.objects.filter(makerspace=space, user=next(iter(members.values()))).first()
    if first is not None:
        membership_titles.assign(manager, first, treasurer, primary=True)
