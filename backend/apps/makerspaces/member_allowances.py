"""A member's own allowances in one space (#234 addendum 3(a)): what is left for THEM.

Every section reuses the owner that enforces it, so the card cannot promise what an action
would refuse: borrowing caps from ``inventory.availability``, included hours from
``bookings.included_hours`` (221d), the sponsor's guest limit and the day-pass caps from the
guest-pass services. A section is ``None`` (or empty) while its module/capability is off.
"""

from django.utils import timezone

from apps.makerspaces.membership_features import membership_feature_on
from apps.makerspaces.platform import module_enabled
from apps.separability.registry import runtime_active

WARNING_AT = 80


def _meter(used, limit):
    """``{used, limit, remaining, percent, level}``; ``limit`` None = no cap."""
    if limit is None:
        return {"used": used, "limit": None, "remaining": None, "percent": None, "level": "ok"}
    percent = 100.0 if limit <= 0 else round(used * 100 / limit, 1)
    level = "limit" if percent >= 100 else "warning" if percent >= WARNING_AT else "ok"
    return {"used": used, "limit": limit, "remaining": max(0, limit - used), "percent": percent, "level": level}


def _borrowing(makerspace, member):
    from apps.inventory import availability

    caps = availability.borrower_allowance(makerspace, member)
    if caps is None:
        return None
    return {name: _meter(value["used"], value["limit"]) for name, value in caps.items()}


def _guest_passes(makerspace, member, now):
    if not membership_feature_on(makerspace, "guest_passes"):
        return None
    from apps.makerspaces.guest_pass_issue import _concurrent_guests
    from apps.makerspaces.guest_pass_policy import policy_for

    policy = policy_for(makerspace)
    return _meter(_concurrent_guests(member, makerspace, now), policy.max_concurrent_guests_per_sponsor)


def _day_passes(makerspace, now):
    """Per product: on sale today or sold out. Never a count -- sales figures stay private."""
    if not membership_feature_on(makerspace, "day_passes"):
        return None
    from apps.makerspaces.guest_pass_day import _check_caps, public_products
    from apps.makerspaces.guest_pass_issue import day_window
    from apps.makerspaces.guest_pass_policy import GuestPassError, policy_for

    policy = policy_for(makerspace)
    _start, _end, today = day_window(makerspace, None, now)
    rows = []
    for product in public_products(makerspace):
        try:
            _check_caps(makerspace, product, today, policy)
            available = True
        except GuestPassError:
            available = False
        rows.append({"product_id": product.pk, "name": product.name, "available_today": available})
    return rows


def _included_hours(makerspace, member, now):
    if not (runtime_active("bookings") and module_enabled(makerspace, "bookings")):
        return []
    from apps.bookings.included_hours import member_balances

    return member_balances(makerspace, member, now)


def member_allowances(membership):
    makerspace, member = membership.makerspace, membership.user
    now = timezone.now()
    return {
        "makerspace_id": makerspace.pk,
        "borrowing": _borrowing(makerspace, member),
        "included_hours": _included_hours(makerspace, member, now),
        "guest_passes": _guest_passes(makerspace, member, now),
        "day_passes": _day_passes(makerspace, now),
    }
