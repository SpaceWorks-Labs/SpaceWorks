"""Booking-owned loan context operations with nonblocking scoped locks."""
from django.db import DatabaseError, IntegrityError, transaction
from django.shortcuts import get_object_or_404
from rest_framework.exceptions import APIException, NotFound
from apps.accounts import rbac
from apps.audit import services as audit
from apps.encryption.write_fence import assert_mapped_write_allowed
from apps.hardware_requests.loan_context_access import require_request_actor, safe_id
from apps.hardware_requests.models import HardwareRequest
from apps.makerspaces.guards import require_module, require_module_locked
from apps.makerspaces.loan_context_generations import validate_generations
from apps.makerspaces.models import Makerspace
from apps.tenant_migration.gate_runtime import assert_write_allowed
from . import booking_authority, booking_permissions
from .models import Booking, BookableSpace
from .models_loan_context import BookingLoanContext, MAX_REVISION


class Conflict(APIException):
    status_code = 409
    default_code = "context_conflict"
    default_detail = "Context changed; reload before trying again."

    def __init__(self, detail=None):
        super().__init__({"detail": detail or self.default_detail, "code": self.default_code})


def _booking(actor, space_id, booking_id, permission):
    booking = get_object_or_404(Booking.objects.select_related("space__makerspace"), pk=safe_id(booking_id), space__makerspace_id=space_id)
    if not booking_authority.can(actor, booking.space, permission):
        raise NotFound()
    return booking


class GenerationChanged(Conflict):
    default_code = "context_generation_changed"

class RevisionChanged(Conflict):
    default_code = "context_revision_changed"

class RevisionExhausted(Conflict):
    default_code = "context_revision_exhausted"

class LockBusy(Conflict):
    default_code = "lock_busy"

def _generation(space):
    validate_generations(space.loan_context_generations)
    return space.loan_context_generations["bookings"]


def _view(actor, req, row, intended):
    if row is not None and row.makerspace_id != req.makerspace_id:
        raise NotFound()
    if row and row.active:
        if intended is not None and intended != row.booking_id:
            raise NotFound()
        old = _booking(actor, req.makerspace_id, row.booking_id, booking_permissions.VIEW)
        return {"active": True, "revision": row.revision, "booking_id": safe_id(old.pk),
            "can_write": booking_authority.can(actor, old.space, booking_permissions.MANAGE_RESERVATIONS)}
    if intended is not None:
        target = _booking(actor, req.makerspace_id, intended, booking_permissions.VIEW)
        can_write = booking_authority.can(actor, target.space, booking_permissions.MANAGE_RESERVATIONS)
    elif rbac.can(actor, rbac.Action.MANAGE_BOOKINGS, req.makerspace_id):
        can_write = True
    else:
        raise NotFound()
    return {"active": False, "revision": row.revision if row else 0, "can_write": can_write}


def read(actor, req, intended=None):
    actor = require_request_actor(actor, req)
    require_module(req.makerspace, "bookings")
    row = BookingLoanContext.objects.filter(request=req).first()
    result = _view(actor, req, row, intended)
    if req.status not in {"draft", "pending_approval", "accepted", "issued", "partially_returned"}:
        result["can_write"] = False
    result["generation"] = _generation(req.makerspace)
    return result


def _refuse_event_only_without_event(req):
    """Decision 221b: a booking is not an event; an event-only item needs its event context."""
    from apps.inventory.event_only import refuse_event_only
    products = [item.product for item in req.items.select_related("product")]
    if not any(p.event_only for p in products):
        return
    from django.apps import apps
    if apps.is_installed("apps.events"):
        from apps.events.models_loan_context import EventLoanContext
        if EventLoanContext.objects.filter(request=req, active=True).exists():
            return
    refuse_event_only(products)


def mutate(actor, req, payload, *, delete=False, intended=None):
    snapshot = BookingLoanContext.objects.filter(request=req).values("booking_id", "active", "revision").first()
    expected = snapshot or {"booking_id": None, "active": False, "revision": 0}
    new_id = None if delete else payload["booking_id"]
    booking_ids = sorted({pk for pk in (expected["booking_id"], new_id, intended) if pk is not None})
    observed = dict(Booking.objects.filter(pk__in=booking_ids, space__makerspace_id=req.makerspace_id).values_list("pk", "space_id"))
    if len(observed) != len(booking_ids):
        raise NotFound()
    try:
        with transaction.atomic():
            assert_write_allowed(req.makerspace_id)
            assert_mapped_write_allowed(req.makerspace_id)
            spaces = {x.pk: x for x in BookableSpace.objects.select_for_update(nowait=True, of=("self",)).filter(pk__in=sorted(set(observed.values())), makerspace_id=req.makerspace_id).order_by("pk")}
            if len(spaces) != len(set(observed.values())):
                raise NotFound()
            space = Makerspace.objects.select_for_update(nowait=True, no_key=True, of=("self",)).get(pk=req.makerspace_id)
            require_module_locked(space, "bookings")
            bookings = {x.pk: x for x in Booking.objects.select_for_update(nowait=True, of=("self",)).filter(pk__in=booking_ids).order_by("pk")}
            if len(bookings) != len(booking_ids) or any(bookings[k].space_id != observed[k] for k in booking_ids):
                raise NotFound()  # Same as events: a moved booking is not an oracle.
            locked = HardwareRequest.objects.select_for_update(nowait=True, of=("self",)).get(pk=req.pk, makerspace_id=req.makerspace_id)
            actor = require_request_actor(actor, locked)
            row = BookingLoanContext.objects.select_for_update(nowait=True, of=("self",)).filter(request=locked).first()
            if row is not None and row.makerspace_id != locked.makerspace_id:
                raise NotFound()
            actual = {"booking_id": row.booking_id, "active": row.active, "revision": row.revision} if row else {"booking_id": None, "active": False, "revision": 0}
            # A changed hidden association must not become a revision oracle.
            if actual != expected:
                raise NotFound()

            old_id = actual["booking_id"] if actual["active"] else None
            if delete and old_id and intended != old_id:
                raise NotFound()
            for bid in {old_id, new_id} - {None}:
                if not booking_authority.can(actor, spaces[observed[bid]], booking_permissions.MANAGE_RESERVATIONS):
                    raise NotFound()
            if delete and not old_id:
                if intended is not None:
                    if not booking_authority.can(actor, spaces[observed[intended]], booking_permissions.MANAGE_RESERVATIONS):
                        raise NotFound()
                elif not rbac.can(actor, rbac.Action.MANAGE_BOOKINGS, space.pk):
                    raise NotFound()
            if locked.status not in {"draft", "pending_approval", "accepted", "issued", "partially_returned"}:
                raise Conflict("This request is no longer editable.")
            # Check CAS only after old/new resource authorization to avoid leaking
            # generation/revision information for an inaccessible association.
            if str(payload["expected_generation"]) != _generation(space):
                raise GenerationChanged()
            if payload["expected_revision"] != actual["revision"]:
                raise RevisionChanged()
            if new_id and (not actual["active"] or actual["booking_id"] != new_id) and bookings[new_id].status in {Booking.Status.CANCELLED, Booking.Status.REJECTED, Booking.Status.COMPLETED, Booking.Status.NO_SHOW}:
                raise Conflict("Booking is unavailable.")
            if not delete:
                _refuse_event_only_without_event(locked)
            active = not delete
            if actual["active"] == active and actual["booking_id"] == new_id:
                result = _view(actor, locked, row, intended if delete else None)
                result["generation"] = _generation(space)
                return result
            if actual["revision"] >= MAX_REVISION:
                raise RevisionExhausted("Context revision exhausted.")
            if row is None:
                try:
                    with transaction.atomic():
                        row = BookingLoanContext.objects.create(makerspace=space, request=locked, booking_id=new_id, active=active, revision=1)
                except IntegrityError as exc:
                    raise Conflict() from exc
            else:
                row.booking_id, row.active = new_id, active
                row.revision += 1
                row.save(update_fields=["booking", "active", "revision", "updated_at"])
            audit.record(actor, "loan.booking_context_changed", makerspace=space, target=locked,
                meta={"operation": "unlinked" if delete else "updated" if actual["active"] else "linked", "domain": "booking"})
            from apps.integrations.link_webhooks import link_changes, link_webhook
            old_booking = actual["booking_id"] if actual["active"] else None
            for event_name, booking_id in link_changes("booking_loan", old_booking, new_id, delete):
                link_webhook(space, event_name, booking_id=booking_id, request_id=locked.pk)
            result = _view(actor, locked, row, None if not delete else intended)
            result["generation"] = _generation(space)
            return result
    except DatabaseError as exc:
        if (getattr(exc.__cause__, "sqlstate", None) or getattr(exc.__cause__, "pgcode", None)) == "55P03":
            raise LockBusy("Context is busy; retry after reloading.") from exc
        raise
