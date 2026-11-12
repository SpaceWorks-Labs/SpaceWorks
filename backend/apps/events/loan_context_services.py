"""Event-owned loan context operations; all writes are serialized and scoped."""
from django.utils.translation import gettext
from django.db import DatabaseError, IntegrityError, transaction
from django.shortcuts import get_object_or_404
from rest_framework.exceptions import APIException, NotFound
from apps.accounts import rbac
from apps.accounts.loan_context_identity import borrower_aliases
from apps.audit import services as audit
from apps.encryption.write_fence import assert_mapped_write_allowed
from apps.hardware_requests.loan_context_access import require_request_actor, safe_id
from apps.hardware_requests.models import HardwareRequest
from apps.makerspaces.guards import require_module, require_module_locked
from apps.makerspaces.loan_context_generations import validate_generations
from apps.makerspaces.models import Makerspace
from apps.tenant_migration.gate_runtime import assert_write_allowed
from . import event_authority, event_permissions
from .models import Event, EventRegistration
from .models_loan_context import EventLoanContext, MAX_REVISION


class Conflict(APIException):
    status_code = 409
    default_code = "context_conflict"
    default_detail = "Context changed; reload before trying again."

    def __init__(self, detail=None):
        super().__init__({"detail": detail or self.default_detail, "code": self.default_code})


def _borrower_aliases(borrower):
    try:
        return borrower_aliases(borrower)
    except (ValueError, RuntimeError):
        raise NotFound() from None

def _event(actor, space_id, event_id, permission):
    event = get_object_or_404(Event.objects.filter(makerspace_id=space_id), pk=safe_id(event_id))
    if not event_authority.can(actor, event, permission):
        raise NotFound()
    return event


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
    return space.loan_context_generations["events"]


def _view(actor, req, row, intended):
    if row is not None and row.makerspace_id != req.makerspace_id:
        raise NotFound()
    if row and row.active:
        if intended is not None and intended != row.event_id:
            raise NotFound()
        old = _event(actor, req.makerspace_id, row.event_id, event_permissions.VIEW)
        if row.participant_registration_id and not EventRegistration.objects.filter(
            pk=row.participant_registration_id, event_id=row.event_id, member_id__in=_borrower_aliases(req.requester)
        ).exists():
            raise NotFound()
        may_participant = event_authority.can(actor, old, event_permissions.MANAGE_REGISTRATIONS)
        # Uniform permission avoids disclosing whether a hidden participant exists.
        can_write = event_authority.can(actor, old, event_permissions.MANAGE_REGISTRATIONS)
        result = {"active": True, "revision": row.revision, "event_id": safe_id(old.pk),
                  "may_view_participant": may_participant, "can_write": can_write}
        if may_participant:
            result["participant_registration_id"] = safe_id(row.participant_registration_id) if row.participant_registration_id else None
        return result
    if intended is not None:
        target = _event(actor, req.makerspace_id, intended, event_permissions.VIEW)
        can_write = event_authority.can(actor, target, event_permissions.MANAGE_REGISTRATIONS)
    elif rbac.can(actor, rbac.Action.MANAGE_EVENTS, req.makerspace_id):
        can_write = True
    else:
        raise NotFound()
    return {"active": False, "revision": row.revision if row else 0, "can_write": can_write}


def read(actor, req, intended=None):
    actor = require_request_actor(actor, req)
    require_module(req.makerspace, "events")
    row = EventLoanContext.objects.filter(request=req).first()
    result = _view(actor, req, row, intended)
    if req.status not in {"draft", "pending_approval", "accepted", "issued", "partially_returned"}:
        result["can_write"] = False
    result["generation"] = _generation(req.makerspace)
    return result


def mutate(actor, req, payload, *, delete=False, intended=None):
    snapshot = EventLoanContext.objects.filter(request=req).values("event_id", "participant_registration_id", "active", "revision").first()
    expected = snapshot or {"event_id": None, "participant_registration_id": None, "active": False, "revision": 0}
    new_id = None if delete else payload["event_id"]
    event_ids = sorted({pk for pk in (expected["event_id"], new_id, intended) if pk is not None})
    try:
        with transaction.atomic():
            assert_write_allowed(req.makerspace_id)
            assert_mapped_write_allowed(req.makerspace_id)
            events = {x.pk: x for x in Event.objects.select_for_update(nowait=True, of=("self",)).filter(pk__in=event_ids, makerspace_id=req.makerspace_id).order_by("pk")}
            if len(events) != len(event_ids):
                raise NotFound()
            space = Makerspace.objects.select_for_update(nowait=True, no_key=True, of=("self",)).get(pk=req.makerspace_id)
            require_module_locked(space, "events")
            registration_ids = sorted({pk for pk in (expected["participant_registration_id"], payload.get("participant_registration_id")) if pk is not None})
            registrations = {x.pk: x for x in EventRegistration.objects.select_for_update(nowait=True, of=("self",)).filter(pk__in=registration_ids).order_by("pk")}
            if len(registrations) != len(registration_ids):
                raise NotFound()
            locked = HardwareRequest.objects.select_for_update(nowait=True, of=("self",)).get(pk=req.pk, makerspace_id=req.makerspace_id)

            actor = require_request_actor(actor, locked)
            row = EventLoanContext.objects.select_for_update(nowait=True, of=("self",)).filter(request=locked).first()
            if row is not None and row.makerspace_id != locked.makerspace_id:
                raise NotFound()
            actual = {"event_id": row.event_id, "participant_registration_id": row.participant_registration_id, "active": row.active, "revision": row.revision} if row else {"event_id": None, "participant_registration_id": None, "active": False, "revision": 0}
            # A changed hidden association must not become a revision oracle.
            if actual != expected:
                raise NotFound()

            old_id = actual["event_id"] if actual["active"] else None
            if delete and old_id and intended != old_id:
                raise NotFound()
            if delete and old_id:
                # Decision 221b: an event-only item keeps its event context for the whole loan.
                from apps.inventory.event_only import refuse_event_only
                refuse_event_only(item.product for item in locked.items.select_related("product"))
            for eid in {old_id, new_id} - {None}:
                if not event_authority.can(actor, events[eid], event_permissions.MANAGE_REGISTRATIONS):
                    raise NotFound()
            if delete and not old_id:
                if intended is not None:
                    if not event_authority.can(actor, events[intended], event_permissions.MANAGE_REGISTRATIONS):
                        raise NotFound()
                elif not rbac.can(actor, rbac.Action.MANAGE_EVENTS, space.pk):
                    raise NotFound()
            old_participant = expected["participant_registration_id"]
            if old_participant is not None:
                registration = registrations[old_participant]
                if registration.event_id != expected["event_id"] or registration.member_id not in _borrower_aliases(locked.requester):
                    raise NotFound()
            if locked.status not in {"draft", "pending_approval", "accepted", "issued", "partially_returned"}:
                raise Conflict(gettext("This request is no longer editable."))
            # Check CAS only after old/new resource authorization to avoid leaking
            # generation/revision information for an inaccessible association.
            if str(payload["expected_generation"]) != _generation(space):
                raise GenerationChanged()
            if payload["expected_revision"] != actual["revision"]:
                raise RevisionChanged()
            if new_id and (not actual["active"] or actual["event_id"] != new_id or actual["participant_registration_id"] != payload.get("participant_registration_id")) and events[new_id].status in {Event.Status.CANCELLED, Event.Status.COMPLETED}:
                raise Conflict(gettext("Event is unavailable."))
            participant_id = payload.get("participant_registration_id") if not delete else None
            if participant_id:
                participant = registrations[participant_id]
                if participant.event_id != new_id or participant.member_id not in _borrower_aliases(locked.requester) or participant.member_id is None:
                    raise NotFound()
                if (actual["event_id"] != new_id or actual["participant_registration_id"] != participant_id) and participant.status not in {EventRegistration.Status.REGISTERED, EventRegistration.Status.ATTENDED}:
                    raise Conflict(gettext("Participant is unavailable."))
            active = not delete
            if actual["active"] == active and actual["event_id"] == new_id and actual["participant_registration_id"] == participant_id:
                result = _view(actor, locked, row, intended if delete else None)
                result["generation"] = _generation(space)
                return result
            if actual["revision"] >= MAX_REVISION:
                raise RevisionExhausted(gettext("Context revision exhausted."))
            if row is None:
                try:
                    with transaction.atomic():
                        row = EventLoanContext.objects.create(makerspace=space, request=locked, event_id=new_id, participant_registration_id=participant_id, active=active, revision=1)
                except IntegrityError as exc:
                    raise Conflict() from exc
            else:
                row.event_id, row.participant_registration_id, row.active = new_id, participant_id, active
                row.revision += 1
                row.save(update_fields=["event", "participant_registration", "active", "revision", "updated_at"])
            audit.record(actor, "loan.event_context_changed", makerspace=space, target=locked,
                meta={"operation": "unlinked" if delete else "updated" if actual["active"] else "linked", "domain": "event"})
            from apps.integrations.link_webhooks import link_changes, link_webhook
            for event_name, event_id in link_changes("event_loan", old_id, new_id, delete):
                link_webhook(space, event_name, event_id=event_id, request_id=locked.pk)
            result = _view(actor, locked, row, None if not delete else intended)
            result["generation"] = _generation(space)
            return result
    except DatabaseError as exc:
        if (getattr(exc.__cause__, "sqlstate", None) or getattr(exc.__cause__, "pgcode", None)) == "55P03":
            raise LockBusy(gettext("Context is busy; retry after reloading.")) from exc
        raise
