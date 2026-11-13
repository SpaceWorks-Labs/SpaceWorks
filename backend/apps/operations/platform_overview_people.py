"""People and lending blocks of the platform overview (#183A). Counts only, no names."""

from django.db.models import Q

from apps.makerspaces.platform import feature_enabled
from apps.operations.platform_overview_blocks import (
    Block, Metric, always_on, count_by_space, in_window,
)

#: Staff roles shown as their own column; anything else (retired kinds) is "other".
STAFF_ROLES = (
    ("space_manager", "Space managers"), ("inventory_manager", "Inventory managers"),
    ("machine_manager", "Machine managers"), ("event_manager", "Event managers"),
    ("booking_manager", "Booking managers"), ("handover", "Handover staff"),
    ("technician", "Technicians"), ("shop_manager", "Shop managers"), ("fundraising", "Fundraising staff"),
    ("custom", "Custom-role staff"),
)


def _people(ids, window, now):
    from apps.accounts.staff_identity import person_q
    from apps.makerspaces.models import MakerspaceMembership

    live = Q(status="active", user__is_active=True) & person_q("user__")
    members = MakerspaceMembership.objects.filter(makerspace_id__in=ids)
    staff = MakerspaceMembership.staff_tracks.filter(makerspace_id__in=ids).filter(live)
    data = {
        "members": count_by_space(members.filter(live)),
        "new_members": count_by_space(in_window(members, "created_at", window)),
        "staff": count_by_space(staff),
    }
    known = [role for role, _label in STAFF_ROLES]
    for role in known:
        data[f"staff_{role}"] = count_by_space(staff.filter(role=role))
    data["staff_other"] = count_by_space(staff.exclude(role__in=known))
    return data


def _people_platform(window, now):
    from apps.accounts.models import User
    from apps.accounts.staff_identity import person_q

    accounts = User.objects.filter(person_q(), is_tenant_dump_stub=False, is_walk_in=False, is_active=True)
    return {"accounts": accounts.count(),
            "new_accounts": in_window(accounts, "date_joined", window).count()}


PEOPLE = Block(
    key="people", label="People", switches=(), gate=always_on,
    metrics=(
        Metric("members", "Active members", timing="snapshot"),
        Metric("new_members", "New sign-ups"),
        Metric("staff", "Active staff", timing="snapshot"),
        *(Metric(f"staff_{role}", label, timing="snapshot") for role, label in STAFF_ROLES),
        Metric("staff_other", "Other staff", timing="snapshot"),
    ),
    collect=_people,
    platform_metrics=(
        Metric("accounts", "Person accounts on the platform", timing="snapshot"),
        Metric("new_accounts", "New person accounts"),
    ),
    collect_platform=_people_platform,
)

ACTIVE_LOAN = ("issued", "partially_returned")
CLOSED_LOAN = ("returned", "closed_with_issue")


def _lending(ids, window, now):
    from apps.hardware_requests.models import HardwareRequest
    from apps.inventory.models import InventoryProduct

    requests = HardwareRequest.objects.filter(makerspace_id__in=ids)
    out = requests.filter(status__in=ACTIVE_LOAN)
    # A direct or self-checkout loan is a request too (PublicToolLoan.request is required),
    # so each loan is counted once, overdue by either due date.
    overdue = out.filter(Q(return_due_at__lt=now)
                         | Q(public_tool_loan__returned_at__isnull=True, public_tool_loan__due_at__lt=now))
    return {
        "items": count_by_space(InventoryProduct.objects.filter(makerspace_id__in=ids, is_archived=False)),
        "loans_issued": count_by_space(in_window(requests.filter(issued_at__isnull=False), "issued_at", window)),
        "loans_out": count_by_space(out),
        "overdue": count_by_space(overdue),
        "returns": count_by_space(in_window(requests.filter(status__in=CLOSED_LOAN), "closed_at", window)),
        "pending_requests": count_by_space(requests.filter(status="pending_approval")),
    }


LENDING = Block(
    key="lending", label="Inventory", switches=("loans.enabled",),
    gate=lambda space: feature_enabled(space, "loans.enabled"),
    metrics=(
        Metric("items", "Catalogue items", timing="snapshot"),
        Metric("loans_issued", "Loans issued"),
        Metric("loans_out", "Loans out now", timing="snapshot"),
        Metric("overdue", "Overdue now", timing="snapshot"),
        Metric("returns", "Loans returned"),
        Metric("pending_requests", "Requests awaiting review", timing="snapshot"),
    ),
    collect=_lending,
)
