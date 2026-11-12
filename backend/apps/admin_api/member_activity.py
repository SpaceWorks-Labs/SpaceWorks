"""Decision 242(e) / PE1: the staff "member 360" -- one member's footprint across every area.

Counts and deep links for EVERY area; full rows only for the areas the viewer manages (least privilege: a
`manage_members` holder reached through an organization grant must not read another area's rows). The Space
Manager holds every action, so sees everything. Rows come from rbac-scoped querysets (machine rows narrowed to
the viewer's machine types, charges through the own-area money queue); counts are plain per-member totals.
Each area is isolated: a failing area is reported in `errors`, never a silent zero.
"""

import logging

from django.db.models import Q, Sum

from apps.accounts import rbac

logger = logging.getLogger(__name__)
A = rbac.Action
ROWS = 10


def _row(obj, label, status, at, tab, **filters):
    return {"id": obj.pk, "label": label, "status": status, "at": at,
            "link": {"tab": tab, "filters": {k: str(v) for k, v in filters.items()}}}


def _block(area, count, rows=None, **extra):
    return {"area": area, "count": count, "rows": rows, "rows_visible": rows is not None, **extra}


def _can_any(actor, space, *actions):
    return any(rbac.can(actor, action, space.pk) for action in actions)


def lending(actor, space, user):
    from apps.hardware_requests.models import HardwareRequest

    base = HardwareRequest.objects.filter(makerspace=space, requester=user)
    rows = None
    if _can_any(actor, space, A.VIEW_INVENTORY, A.ACCEPT_REQUEST, A.ISSUE_REQUEST, A.RETURN_REQUEST):
        scoped = rbac.scope_by_makerspace(actor, base).order_by("-pk")[:ROWS]
        rows = [_row(r, f"Request #{r.pk}", r.status, r.created_at, "requests", id=r.pk, history="true") for r in scoped]
    return _block("lending", base.count(), rows, open=base.filter(status__in=("issued", "partially_returned")).count())


def bookings(actor, space, user):
    from apps.bookings.models import Booking

    base = Booking.objects.filter(space__makerspace=space, member=user)
    rows = None
    if rbac.can(actor, A.MANAGE_BOOKINGS, space.pk):
        scoped = rbac.scope_by_action(actor, A.MANAGE_BOOKINGS, base, field="space__makerspace_id").order_by("-starts_at")[:ROWS]
        rows = [_row(b, f"Booking #{b.pk}", b.status, b.starts_at, "bookings", space=b.space_id, booking=b.pk) for b in scoped]
    return _block("bookings", base.count(), rows)


def machines(actor, space, user):
    from apps.machines import role_scope
    from apps.machines.access_scoping import scope_machines_for_actor
    from apps.machines.models import Machine, MachineServiceRequest, MachineSession

    jobs = MachineServiceRequest.objects.filter(makerspace=space).filter(Q(requester=user) | Q(member=user))
    sessions = MachineSession.objects.filter(makerspace=space, member=user)
    rows = None
    if rbac.can(actor, A.MANAGE_MACHINES, space.pk):
        fleet = scope_machines_for_actor(actor, Machine.objects.filter(makerspace=space))
        job_rows = role_scope.scoped_service_requests(actor, jobs, [space.pk]).order_by("-pk")[:ROWS]
        rows = [_row(j, f"Job #{j.pk}", j.status, j.created_at, "machines", job=j.pk) for j in job_rows]
        rows += [_row(s, f"Session #{s.pk}", "ended" if s.ended_at else "running", s.started_at, "machines", session=s.pk)
                 for s in sessions.filter(machine__in=fleet).order_by("-pk")[:ROWS]]
    return _block("machines", jobs.distinct().count() + sessions.count(), rows)


def events(actor, space, user):
    from apps.events.models import EventRegistration

    base = EventRegistration.objects.filter(event__makerspace=space, member=user)
    rows = None
    if rbac.can(actor, A.MANAGE_EVENTS, space.pk):
        scoped = rbac.scope_by_action(actor, A.MANAGE_EVENTS, base, field="event__makerspace_id").select_related(
            "event").order_by("-pk")[:ROWS]
        rows = [_row(r, r.event.title, r.status, r.created_at, "events", event=r.event_id) for r in scoped]
    return _block("events", base.count(), rows)


def shop(actor, space, user):
    from apps.shop.models import ShopOrder

    base = ShopOrder.objects.filter(makerspace=space, buyer=user)
    rows = None
    if rbac.can(actor, A.MANAGE_SHOP, space.pk):
        scoped = rbac.scope_by_action(actor, A.MANAGE_SHOP, base, field="makerspace_id").order_by("-pk")[:ROWS]
        rows = [_row(o, f"Order #{o.pk}", o.status, o.created_at, "shop", order=o.pk) for o in scoped]
    return _block("shop", base.count(), rows)


def money(actor, space, user):
    from apps.payments import area_queue
    from apps.payments.models import Payment

    base = Payment.objects.filter(makerspace=space, member=user)
    pending = base.filter(status=Payment.Status.PENDING)
    owed = {r["currency"]: str(r["total"]) for r in pending.values("currency").annotate(total=Sum("amount"))}
    rows = None
    if area_queue.owned_subject_types(actor, space.pk) != []:
        mine = area_queue.area_payments(actor, space.pk).filter(member=user).order_by("-pk")[:ROWS]
        rows = [_row(p, p.subject_label or p.get_subject_type_display(), p.status, p.created_at, "payments", payment=p.pk)
                for p in mine]
    return _block("money", base.count(), rows, pending=pending.count(), owed=owed)


def safety(actor, space, user):
    from apps.maintenance.incidents import scope
    from apps.maintenance.incidents.models import Incident

    if not scope.incidents_on(space):
        return None
    rows = None
    if scope.is_staff_reader(actor, space):
        scoped = scope.readable_incidents(actor, space).filter(involved_user=user).order_by("-pk")[:ROWS]
        rows = [_row(i, i.title, i.status, i.occurred_at, "incidents", id=i.pk) for i in scoped]
    return _block("safety", Incident.objects.filter(makerspace=space, involved_user=user).count(), rows)


def people(actor, space, user):
    from apps.makerspaces.models import GuestPass, VolunteerHourEntry
    from apps.machines.models import MachineAccessGrant

    passes = GuestPass.objects.filter(makerspace=space).filter(Q(sponsor=user) | Q(holder=user))
    hours = VolunteerHourEntry.objects.filter(makerspace=space, member=user)
    access = MachineAccessGrant.objects.filter(member=user, makerspace=space, revoked_at__isnull=True)  # decision 319
    rows = None
    if rbac.can(actor, A.MANAGE_MEMBERS, space.pk):
        rows = [_row(p, f"Guest pass ({p.kind})", p.status, p.valid_from, "members", section="guests", pass_id=p.pk)
                for p in passes.order_by("-pk")[:ROWS]]
    return _block("people", passes.count() + hours.count(), rows, guest_passes=passes.count(),
                  volunteer_entries=hours.count(), machine_access=access.count())


AREAS = (lending, bookings, machines, events, shop, money, safety, people)


def build_member_activity(actor, space, user):
    blocks, errors = [], []
    for builder in AREAS:
        try:
            block = builder(actor, space, user)
        except Exception as exc:
            logger.error("Member activity area failed", extra={"makerspace_id": space.pk, "area": builder.__name__,
                                                               "error_type": type(exc).__name__})
            errors.append(builder.__name__)
            continue
        if block is not None:
            blocks.append(block)
    return {"member_id": user.pk, "areas": blocks, "errors": errors}
