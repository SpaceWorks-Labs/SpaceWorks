"""Decision 242(i)(j): "Waiting on me" counters per role and per area (U1, U2, U13).

One counter module for the Space Manager's home and every area manager's home. Each area is built only from
what the ACTOR may act on: an action check, the module/capability switch, and rbac scoping on every queryset
(`scope_by_makerspace`, machine-type scope, the incident reader reach, `area_queue` money ownership). A failing
area is logged and reported in `errors` (never a silent 0), so the client can say "couldn't load Machines".
Counts only, never rows; each item names a console tab plus filters the client turns into a deep link.
"""

import logging
from datetime import timedelta

from django.utils import timezone

from apps.accounts import rbac
from apps.makerspaces.local_time import local_day_bounds, to_local
from apps.makerspaces.platform import feature_enabled, module_enabled

logger = logging.getLogger(__name__)
A = rbac.Action


def item(key, count, tab, **filters):
    return {"key": key, "count": int(count), "link": {"tab": tab, "filters": {k: str(v) for k, v in filters.items()}}}


def _scope(actor, queryset, field="makerspace_id"):
    return rbac.scope_by_makerspace(actor, queryset, makerspace_field=field)


def lending(actor, space, now):
    from apps.hardware_requests.models import HardwareRequest, PublicToolLoan
    from apps.operations.dashboard_due_back import due_back_counts, stock_health_counts
    from apps.operations.models import StocktakeSession
    from apps.hardware_requests.models import PublicProblemReport

    if not feature_enabled(space, "loans.enabled"):
        return []
    can, out = (lambda action: rbac.can(actor, action, space.pk)), []
    requests = _scope(actor, HardwareRequest.objects.filter(makerspace=space))
    if can(A.ACCEPT_REQUEST):
        out.append(item("pending_requests", requests.filter(status=HardwareRequest.Status.PENDING_APPROVAL).count(),
                        "requests", queue="pending"))
    if can(A.ISSUE_REQUEST):
        out.append(item("awaiting_issue", requests.filter(status=HardwareRequest.Status.ACCEPTED).count(),
                        "requests", queue="accepted"))
    if can(A.RETURN_REQUEST) or can(A.VIEW_INVENTORY):
        direct = _scope(actor, PublicToolLoan.objects.filter(makerspace=space, returned_at__isnull=True))
        overdue = requests.filter(
            status__in=("issued", "partially_returned"), return_due_at__lt=now,
        ).exclude(pk__in=direct.values("request_id")).count() + direct.filter(due_at__lt=now).count()
        due = due_back_counts(actor, space, now)
        out += [item("overdue_loans", overdue, "ledger", overdue="true"),
                item("due_today_loans", due["due_today_loans"], "ledger", due="today"),
                item("due_soon_loans", due["due_soon_loans"], "ledger", due="soon")]
    if can(A.VIEW_INVENTORY):
        health = stock_health_counts(actor, space)
        out += [item("open_problem_reports", _scope(actor, PublicProblemReport.objects.filter(
                    makerspace=space, resolved_at__isnull=True)).count(), "needsfix", section="problems"),
                item("true_low_stock", health["true_low_stock"], "inventory", low_stock="true"),
                item("in_repair", health["in_repair"], "needsfix")]
        if module_enabled(space, "stocktake"):
            out.append(item("stocktakes_awaiting_approval", _scope(actor, StocktakeSession.objects.filter(
                makerspace=space, status=StocktakeSession.Status.COMPLETED)).count(), "stocktake", status="completed"))
    return out


def machines(actor, space, now):
    from apps.machines import role_scope
    from apps.machines.access_scoping import scope_machines_for_actor
    from apps.machines.models import CertificationGrant, Machine, MachineServiceRequest

    if not module_enabled(space, "machines"):
        return []
    out = []
    if rbac.can(actor, A.MANAGE_MACHINES, space.pk):
        fleet = scope_machines_for_actor(actor, Machine.objects.filter(makerspace=space, is_active=True))
        out.append(item("machines_down", fleet.filter(status__in=(Machine.Status.OFFLINE, Machine.Status.MAINTENANCE)
                                                     ).count(), "machines", status="down"))
        if module_enabled(space, "machine_service"):
            jobs = role_scope.scoped_service_requests(
                actor, _scope(actor, MachineServiceRequest.objects.filter(makerspace=space)), [space.pk])
            for key, status in (("jobs_to_review", "pending"), ("jobs_in_progress", "in_progress"),
                                ("jobs_awaiting_collection", "completed")):
                out.append(item(key, jobs.filter(status=status).count(), "machines", work_queue=key))
        if feature_enabled(space, "machines.maintenance"):
            from apps.maintenance.models import MaintenanceSchedule
            schedules = MaintenanceSchedule.objects.filter(
                machine__in=fleet, is_active=True, next_due__lt=to_local(space, now).date())
            out.append(item("maintenance_overdue", schedules.count(), "machines", work_queue="maintenance_overdue"))
        soon = CertificationGrant.objects.filter(
            certification_type__machine_type_id__in=fleet.values("machine_type_id"), revoked_at__isnull=True,
            expires_at__gte=now, expires_at__lt=now + timedelta(days=30)).distinct()
        out.append(item("certifications_expiring", soon.count(), "machines", expiring="30"))
    out += _technician_items(actor, space)
    return out


def _technician_items(actor, space):
    """A Technician's own work: open repairs and work orders assigned to them."""
    if not rbac.can(actor, A.WORK_REPAIRS, space.pk):
        return []
    from apps.maintenance.models import IssueReport, WorkOrder
    from apps.maintenance.repairs.authority import assigned_q

    mine = IssueReport.objects.filter(makerspace=space, state__in=IssueReport.OPEN_STATES).filter(
        assigned_q(actor)).distinct().count()
    orders = WorkOrder.objects.filter(makerspace=space, status__in=WorkOrder.OPEN_STATUSES, assignee_id=actor.pk).count()
    return [item("my_open_repairs", mine, "repairs", assigned="me"), item("my_work_orders", orders, "repairs")]


def events(actor, space, now):
    from apps.events.models import Event, EventRegistration

    if not (module_enabled(space, "events") and rbac.can(actor, A.MANAGE_EVENTS, space.pk)):
        return []
    rows = rbac.scope_by_action(actor, A.MANAGE_EVENTS, EventRegistration.objects.filter(event__makerspace=space),
                                field="event__makerspace_id")
    start, end = local_day_bounds(space, to_local(space, now).date())[0], local_day_bounds(
        space, to_local(space, now).date() + timedelta(days=1))[0]
    today = rbac.scope_by_action(actor, A.MANAGE_EVENTS, Event.objects.filter(
        makerspace=space, status=Event.Status.PUBLISHED, starts_at__lt=end, ends_at__gte=start))
    return [item("pending_event_registrations", rows.filter(status="pending_approval").count(), "events"),
            item("waitlisted_registrations", rows.filter(status="waitlisted", event__ends_at__gt=now).count(),
                 "events", queue="waitlist"),
            item("events_today", today.count(), "events", status="published")]


def bookings(actor, space, now):
    from apps.bookings.models import Booking
    from apps.bookings.models_departure import BookingIssue
    from apps.maintenance.models import RoomOutage

    if not (module_enabled(space, "bookings") and rbac.can(actor, A.MANAGE_BOOKINGS, space.pk)):
        return []
    rows = rbac.scope_by_action(actor, A.MANAGE_BOOKINGS, Booking.objects.filter(space__makerspace=space),
                                field="space__makerspace_id")
    start = local_day_bounds(space, to_local(space, now).date())[0]
    end = start + timedelta(days=1)
    out = [item("pending_bookings", rows.filter(status=Booking.Status.PENDING).count(), "bookings", status="pending"),
           item("bookings_today", rows.filter(status=Booking.Status.CONFIRMED, starts_at__lt=end, ends_at__gte=start
                                              ).count(), "bookings", status="confirmed"),
           item("open_booking_issues", rbac.scope_by_action(actor, A.MANAGE_BOOKINGS, BookingIssue.objects.filter(
               makerspace=space, resolved_at__isnull=True), field="makerspace_id").count(), "bookings", view="issues")]
    if feature_enabled(space, "bookings.room_maintenance"):
        out.append(item("room_outages_week", RoomOutage.objects.filter(
            makerspace=space, ended_at__isnull=True, started_at__lt=now + timedelta(days=7)).count(), "bookings"))
    return out


def shop(actor, space, now):
    from apps.shop.models import ShopOrder

    if not (module_enabled(space, "shop") and rbac.can(actor, A.MANAGE_SHOP, space.pk)):
        return []
    orders = rbac.scope_by_action(actor, A.MANAGE_SHOP, ShopOrder.objects.filter(makerspace=space), field="makerspace_id")
    Status = ShopOrder.Status
    return [item("shop_awaiting_payment", orders.filter(status=Status.AWAITING_PAYMENT).count(), "shop", status="awaiting_payment"),
            item("shop_to_prepare", orders.filter(status=Status.PAID).count(), "shop", status="paid"),
            item("shop_ready_for_pickup", orders.filter(status=Status.READY).count(), "shop", status="ready"),
            item("shop_unfulfilled", orders.filter(status=Status.UNFULFILLED).count(), "shop", status="unfulfilled")]


def people(actor, space, now):
    from apps.makerspaces.models import GuestPass, MembershipErasureRequest, MembershipRequest, VolunteerHourEntry

    if not rbac.can(actor, A.MANAGE_MEMBERS, space.pk):
        return []
    scope = lambda qs: rbac.scope_by_action(actor, A.MANAGE_MEMBERS, qs, field="makerspace_id")  # noqa: E731
    out = [item("membership_requests", scope(MembershipRequest.objects.filter(
        makerspace=space, kind="request", state__in=("requested", "awaiting_vouches", "awaiting_payment"))).count(),
        "members", section="requests"),
        item("erasure_requests", scope(MembershipErasureRequest.objects.filter(
            makerspace=space, status="requested")).count(), "members", section="tools")]
    if feature_enabled(space, "membership.guest_passes"):
        today = to_local(space, now).date()
        out.append(item("guest_passes_today", scope(GuestPass.objects.filter(
            makerspace=space, status__in=GuestPass.LIVE_STATUSES, pass_date=today)).count(), "members", section="guests"))
    if feature_enabled(space, "membership.volunteer_credit"):
        out.append(item("volunteer_hours_pending", scope(VolunteerHourEntry.objects.filter(
            makerspace=space, status="pending")).count(), "members", section="volunteering"))
    return out


def money(actor, space, now):
    from apps.payments import area_queue
    from apps.payments.models import RefundCase

    owned = area_queue.owned_subject_types(actor, space.pk)
    if owned == []:
        return []
    groups = area_queue.summary(actor, space, now)
    out = [item("payments_pending", sum(g["pending"] for g in groups), "payments", status="pending"),
           item("payments_overdue", sum(g["overdue"] for g in groups), "payments", due_state="overdue"),
           item("paid_claims_waiting", sum(g["claims"] for g in groups), "payments", view="claims")]
    cases = RefundCase.objects.filter(makerspace=space, status__in=RefundCase.ACTIVE_STATUSES)
    if owned is not None:
        cases = cases.filter(payment__subject_type__in=owned)
    out.append(item("refund_cases_open", cases.count(), "refunds"))
    return out


def safety(actor, space, now):
    from apps.maintenance.incidents import scope
    from apps.maintenance.incidents.models import Incident

    if not (scope.incidents_on(space) and scope.can_record(actor, space)):
        return []
    return [item("open_incidents", scope.visible_incidents(actor, space).filter(
        status__in=Incident.OPEN_STATUSES).count(), "incidents", status="open")]


AREAS = (("lending", lending), ("machines", machines), ("events", events), ("bookings", bookings), ("shop", shop),
         ("people", people), ("money", money), ("safety", safety))


def build_attention(actor, space, *, area=None, now=None):
    """`{"areas": [...], "waiting": [...], "errors": [...]}` for one actor in one space."""
    now = now or timezone.now()
    areas, errors = [], []
    for key, builder in AREAS:
        if area and key != area:
            continue
        try:
            items = builder(actor, space, now)
        except Exception as exc:  # one failing area must not blank the whole home (U13)
            logger.error("Attention counter failed", extra={"makerspace_id": space.pk, "area": key,
                                                            "error_type": type(exc).__name__})
            errors.append(key)
            continue
        if items:
            areas.append({"key": key, "total": sum(row["count"] for row in items), "items": items})
    waiting = sorted(({"area": group["key"], **row} for group in areas for row in group["items"] if row["count"]),
                     key=lambda row: -row["count"])
    return {"areas": areas, "waiting": waiting, "errors": errors}
