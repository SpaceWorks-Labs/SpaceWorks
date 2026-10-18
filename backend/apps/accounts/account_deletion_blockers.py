"""The shared preview/locked account-deletion predicates; no module enablement gates."""

from collections import Counter
from decimal import Decimal

from django.apps import apps
from django.db.models import Q, Sum
from django.utils import timezone

from apps.accounts import rbac
from apps.accounts.models import User
from apps.accounts.rbac_roles import additional_roles_prefetch
from apps.makerspaces.models import MakerspaceMembership
from apps.organizations.models import Organization, OrganizationMembership
from apps.organizations.services_console import OrganizationConflict
from apps.organizations.services_governance import assert_governor_remains
from apps.payments.models import Payment, Refund


def blocker(code, *, makerspace_id=None, organization_id=None, count=1, detail):
    from django.conf import settings
    from apps.makerspaces.models import Makerspace
    from apps.makerspaces.website_directory import public_url
    space = Makerspace.objects.filter(pk=makerspace_id).first() if makerspace_id else None
    return {"code": code, "makerspace_id": makerspace_id, "organization_id": organization_id,
            "makerspace_slug": space.slug if space else None,
            "makerspace_member_url": public_url(space, "member", "").rstrip("/") if space else None,
            "organization_url": f"{settings.PUBLIC_APP_BASE_URL.rstrip('/')}/admin/organizations" if organization_id else None,
            "count": count, "detail": detail}


def _counts(label, user, filters, tenant="makerspace_id", owner="member", ownership=None):
    try:
        model = apps.get_model(label)
    except LookupError:
        return Counter()
    rows = model.objects.filter(ownership if ownership is not None else Q(**{owner: user}), **filters)
    return Counter(rows.values_list(tenant, flat=True))


def collect(user, *, now=None, gated=(), organizations=None):
    """Caller holds all domain locks for Stage A, or an atomic preview transaction."""
    now = now or timezone.now()
    result = []
    predicates = (
        ("unpaid_charges", "payments.Payment", {"status": "pending"}, "makerspace_id", "member",
         "Settle all outstanding charges."),
        ("refund_in_progress", "payments.Refund", {"status": "pending"}, "payment__makerspace_id", "payment__member",
         "Wait for pending refunds to finish."),
        ("active_loans", "hardware_requests.HardwareRequest", {"status__in": ("issued", "partially_returned")},
         "makerspace_id", "requester", "Return all borrowed hardware."),
        ("active_loans", "hardware_requests.PublicToolLoan", {"status": "checked_out"},
         "makerspace_id", "requester", "Return all borrowed hardware."),
        ("open_requests", "hardware_requests.HardwareRequest", {"status__in": ("draft", "pending_approval", "accepted")},
         "makerspace_id", "requester", "Close open hardware requests."),
        ("problem_report_open", "hardware_requests.PublicProblemReport", {"resolved_at__isnull": True},
         "makerspace_id", "requester", "Ask staff to resolve open problem reports."),
        ("upcoming_bookings", "bookings.Booking", {"status__in": ("pending", "confirmed"), "ends_at__gt": now},
         "space__makerspace_id", "member", "Cancel or finish upcoming bookings."),
        ("upcoming_registrations", "events.EventRegistration",
         {"status__in": ("pending_approval", "registered", "waitlisted"),
          "event__status__in": ("draft", "published"), "event__ends_at__gt": now},
         "event__makerspace_id", "member", "Cancel or finish upcoming event registrations."),
    )
    totals, details = Counter(), {}
    for code, label, filters, tenant, owner, detail in predicates:
        for tenant_id, count in _counts(label, user, filters, tenant, owner).items():
            totals[code, tenant_id] += count
            details[code] = detail
    for (code, tenant_id), count in totals.items():
        result.append(blocker(code, makerspace_id=tenant_id, count=count, detail=details[code]))
    jobs = _counts("machines.MachineServiceRequest", user,
                   {"status__in": ("pending", "accepted", "in_progress", "completed")},
                   ownership=Q(member=user) | Q(member__isnull=True, requester=user))
    for tenant_id, count in jobs.items():
        result.append(blocker("open_service_jobs", makerspace_id=tenant_id, count=count,
                              detail="Finish and collect outstanding machine service jobs."))
    deposits = Counter()
    for payment in Payment.objects.filter(member=user, subject_type="loan_deposit",
                                          status__in=("paid_online", "paid_offline")):
        returned = Refund.objects.filter(payment=payment, status="succeeded", amended_by__isnull=True)
        total = returned.aggregate(total=Sum("amount"))["total"] or Decimal("0")
        if total < payment.amount:
            deposits[payment.makerspace_id] += 1
    for tenant_id, count in deposits.items():
        result.append(blocker("deposit_held", makerspace_id=tenant_id, count=count,
                              detail="Ask staff to return held loan deposits."))
    if user.access_status != User.AccessStatus.ACTIVE:
        result.append(blocker("access_restricted", detail="Ask staff to resolve the account restriction."))
    result.extend(_manager_blockers(user))
    result.extend(_governor_blockers(user, organizations))
    result.extend(blocker("makerspace_gated", makerspace_id=pk,
                          detail="This makerspace is temporarily unavailable for account changes.") for pk in sorted(gated))
    if user.is_superuser or user.role == User.Role.SUPERADMIN:
        result.append(blocker("superadmin", detail="Superadmin accounts cannot request account deletion."))
    return sorted(result, key=lambda row: (row["code"], row["makerspace_id"] or 0, row["organization_id"] or 0))


def _manager_blockers(user):
    # Exactly the leave_makerspace action-holder rule, including active account,
    # restriction and dump-stub filters for replacement managers.
    memberships = MakerspaceMembership.objects.filter(user=user, status="active").select_related("assigned_role")
    for membership in memberships.prefetch_related(additional_roles_prefetch()):
        if rbac.Action.MANAGE_MAKERSPACE not in rbac.actions_for_membership(membership):
            continue
        others = MakerspaceMembership.objects.filter(
            makerspace_id=membership.makerspace_id, status="active", user__is_active=True,
            user__access_status="active", user__is_tenant_dump_stub=False,
        ).exclude(pk=membership.pk).select_related("assigned_role").prefetch_related(additional_roles_prefetch())
        if not any(rbac.Action.MANAGE_MAKERSPACE in rbac.actions_for_membership(row) for row in others):
            yield blocker("last_manager", makerspace_id=membership.makerspace_id,
                          detail="Assign another makerspace manager before deleting your account.")


def _governor_blockers(user, organizations):
    if organizations is None:
        ids = OrganizationMembership.objects.filter(user=user).values("organization_id")
        organizations = Organization.objects.filter(pk__in=ids).order_by("pk")
    for organization in organizations:
        target = organization.memberships.filter(user=user).first()
        if target is None:
            continue
        try:
            assert_governor_remains(organization, replaced_id=target.pk, status="suspended")
        except OrganizationConflict:
            yield blocker("last_org_governor", organization_id=organization.pk,
                          detail="Assign another organization governor before deleting your account.")
