"""Event equipment planning over the event's dates (decision 221b).

Read side: `window_rows` asks the inventory availability owner (`window_availability`)
how many units are free between the event start and the moment its loans fall due; this
module never counts stock itself. Write side: `set_return_hours` stores the event's return
window and `plan_for_participants` creates one pending request per participant through the
normal contextual staff intake, so every issue still records one accountable borrower.
"""
import uuid
from datetime import timedelta

from django.core.exceptions import ValidationError as DjangoValidationError
from django.db import transaction
from django.http import Http404
from django.shortcuts import get_object_or_404
from rest_framework.exceptions import APIException, NotFound

from apps.accounts import rbac
from apps.audit.services import record
from apps.inventory import availability
from apps.inventory.models import InventoryProduct
from apps.makerspaces.guards import require_feature, require_module

from . import event_authority, event_permissions
from .guest_pass_adapter import ensure_event_pass
from .models import Event
from apps.presence.guard import MemberPresenceRequired, PresenceRequired, WaiverAcceptanceRequired

from .services_write_boundary import write_boundary

_GUARD_REFUSALS = (MemberPresenceRequired, PresenceRequired, WaiverAcceptanceRequired)

MAX_PRODUCTS = 50
MAX_PARTICIPANTS = 50
LIMITED_SHARE = 0.2


def planning_event(actor, makerspace_id, event_id, permission=event_permissions.MANAGE_REGISTRATIONS):
    """The event, only while it is open for planning and `actor` holds `permission` on it."""
    event = get_object_or_404(Event.objects.select_related("makerspace"), pk=event_id, makerspace_id=makerspace_id)
    # Module switches answer first: with Events off the authority check below fails closed to a bare 404.
    require_module(event.makerspace, "events")
    require_module(event.makerspace, "request_workflow")
    if (event.status in {Event.Status.CANCELLED, Event.Status.COMPLETED}
            or not event_authority.can(actor, event, permission)):
        raise NotFound()
    require_feature(event.makerspace, "loans.enabled")
    return event


def event_window(event):
    """`(starts_at, return_due_at)`: loans taken for the event are out until it ends plus the return window."""
    ends = event.ends_at or event.starts_at
    from apps.hardware_requests.due_policy import effective_due
    # m11: the same due the loan will really get (rolled to the next open session), so planning matches issue.
    return event.starts_at, effective_due(event.makerspace, ends + timedelta(hours=event.equipment_return_hours or 0))


def _status(free, lendable):
    if free <= 0 or lendable <= 0:
        return "unavailable"
    return "limited" if free <= -(-lendable * 2 // 10) else "available"


def window_rows(actor, event, product_ids):
    """Rows for the requested event-context products; counts only for inventory-view staff."""
    ids = list(dict.fromkeys(product_ids))[:MAX_PRODUCTS]
    products = list(InventoryProduct.objects.filter(
        makerspace_id=event.makerspace_id, pk__in=ids, is_public=True, is_archived=False,
        is_consumable=False).order_by("pk"))
    starts, due = event_window(event)
    figures = availability.window_availability(products, starts, due)
    counts = rbac.can(actor, rbac.Action.VIEW_INVENTORY, event.makerspace_id)
    rows = []
    for product in products:
        fig = figures[product.pk]
        row = {"product_id": product.pk, "name": product.name, "event_only": product.event_only,
               "status": _status(fig["free"], fig["lendable"])}
        if counts:
            row.update(free=fig["free"], committed=fig["committed"],
                       back_before_window=fig["back_before_window"], lendable=fig["lendable"])
        rows.append(row)
    return rows, figures, counts


def set_return_hours(actor, event, hours):
    with write_boundary(event, actor=actor):
        locked = Event.objects.select_for_update(of=("self",)).get(pk=event.pk)
        if locked.equipment_return_hours == hours:
            return locked
        old = locked.equipment_return_hours
        locked.equipment_return_hours = hours
        locked.save(update_fields=["equipment_return_hours"])
        record(actor, "event.equipment_return_window_changed", makerspace=locked.makerspace, target=locked,
               meta={"from_hours": old, "to_hours": hours})
        return locked


def _totals(lines, participants, figures, counts):
    wanted = {}
    for person in participants:
        for line in person["lines"] or lines:
            wanted[line["product_id"]] = wanted.get(line["product_id"], 0) + line["quantity"]
    rows = []
    for product_id, quantity in sorted(wanted.items()):
        fig = figures.get(product_id)
        # Without inventory view the verdict uses the same coarse band as the window rows: a
        # quantity-sensitive ok/short would let repeated dry runs binary-search the free count (#214b).
        enough = bool(fig) and (quantity <= fig["free"] if counts else fig["free"] > 0 and fig["lendable"] > 0)
        row = {"product_id": product_id, "requested": quantity, "status": "ok" if enough else "short"}
        if counts and fig:
            row["free"] = fig["free"]
        rows.append(row)
    return rows


def _error_code(exc):
    if isinstance(exc, Http404):
        return "not_found"
    if isinstance(exc, DjangoValidationError):
        return "invalid"
    if isinstance(exc, APIException):
        detail = exc.detail
        return str(detail.get("code")) if isinstance(detail, dict) and detail.get("code") else str(exc.default_code)
    if isinstance(getattr(exc, "code", None), str):  # presence guard refusals (decision 223 G5)
        return exc.code
    return str(exc) or "conflict"


def plan_for_participants(actor, event, *, operation_id, requested_for, lines, participants, dry_run):
    """One pending request per participant (own borrower, own request); partial success is reported per row."""
    from apps.hardware_requests.contextual_equipment_service import ProposalConflict, create_pending
    ids = [line["product_id"] for person in participants for line in (person["lines"] or lines)]
    _rows, figures, counts = window_rows(actor, event, ids)
    result = {"dry_run": dry_run, "totals": _totals(lines, participants, figures, counts), "results": []}
    if dry_run:
        return result
    from .models import EventRegistration
    # Only this event's registrations: a guest pass is never issued, nor a request bound, for another event's id.
    own = set(EventRegistration.objects.filter(
        event=event, pk__in=[person["registration_id"] for person in participants]).values_list("pk", flat=True))
    # The tenant key is minted before any savepoint: preparing one inside a transaction is refused, and every
    # per-person savepoint below would otherwise turn the whole plan into a 503.
    from apps.encryption.tenant_preparation import prepare_tenant_key, tenant_key_context
    with tenant_key_context(prepare_tenant_key(event.makerspace_id)):
        for person in participants:
            reg_id = person["registration_id"]
            items = [{"product_id": line["product_id"], "quantity": line["quantity"]} for line in person["lines"] or lines]
            row = {"registration_id": reg_id}
            if reg_id not in own:
                row.update(outcome="error", code="not_found")
                result["results"].append(row)
                continue
            try:
                with transaction.atomic():  # one savepoint per person: a refusal never poisons the others
                    # Decision 223: a non-member registrant is planned for through their event guest pass (no
                    # presence needed). m11: inside the savepoint, so a refused row leaves no pass behind.
                    ensure_event_pass(reg_id, issuer_id=actor.pk)
                    outcome, req, replayed = create_pending(
                        makerspace_id=event.makerspace_id, actor=actor, borrower=None, intent_kind="staff",
                        operation_id=uuid.uuid5(operation_id, f"registration:{reg_id}"),
                        event_registration_id=reg_id, booking_id=None, booking_token=None, borrower_id=None,
                        items=items, kit=None, requested_for=requested_for, pickup_from=None, pickup_until=None,
                        waitlist_entry_id=None,
                        canonical_fields={"items": items, "requested_for": requested_for})
                row.update(outcome="replayed" if replayed else "created", request_id=req.pk, status=req.status)
            except (Http404, ProposalConflict, APIException, DjangoValidationError, *_GUARD_REFUSALS) as exc:
                # Decision 223 G5: before the event nobody has a presence session, and a registrant may hold no
                # membership. Those refusals are per-row results, never an abort of the whole plan.
                row.update(outcome="error", code=_error_code(exc))
            result["results"].append(row)
    created = sum(1 for row in result["results"] if row["outcome"] == "created")
    if created:  # m11: a pure replay changed nothing, so it writes no second audit entry
        record(actor, "event.equipment_planned", makerspace=event.makerspace, target=event,
               meta={"participants": len(participants), "created": created})
    return result
