"""Transactional contextual request orchestration; entrypoints must validate input."""
import json
from django.core.exceptions import ValidationError
from django.db import DatabaseError, IntegrityError, transaction
from django.http import Http404

from apps.accounts.account_obligations import lock_obligation_owner
from apps.accounts.loan_context_identity import borrower_aliases, borrower_survivor
from apps.accounts.models import User
from apps.accounts.staff_identity import is_person, is_platform
from apps.encryption.write_fence import assert_mapped_write_allowed
from apps.encryption.tenant_preparation import prepare_tenant_key, tenant_key_context
from apps.hardware_requests.request_submission_locked import submit_locked
from apps.hardware_requests.request_workflow import RequesterSnapshot
from apps.inventory.equipment_proposal_receipts import (
    canonical_intent_json, create_receipt, locked_receipt, make_proposal_intent,
    proposal_fingerprint_from_snapshot, receipt_matches,
)
from apps.inventory.event_only import refuse_event_only
from apps.inventory.models import InventoryProduct
from apps.inventory.equipment_kit_validation import public_safe
from apps.inventory.models_equipment_proposals import (
    EquipmentKitAllocation, EquipmentKitTemplate, EquipmentKitVersion, EquipmentProposalReceipt,
)
from apps.makerspaces.guards import require_feature, require_module, require_module_for_servable, require_module_locked
from apps.makerspaces.models import Makerspace
from apps.makerspaces.platform import module_enabled
from apps.makerspaces.request_access import require_current_term
from apps.hardware_requests.guest_lending import admit_borrower
from apps.presence.guard import require_active_account
from apps.separability import equipment_context_bridge as bridge
from apps.tenant_migration.gate_runtime import assert_write_allowed, boundary_tenant_write


from .contextual_equipment_common import ProposalConflict, _aliases, _require_same_outcome


def _create_pending(*, makerspace_id, actor, borrower, intent_kind, operation_id,
                    event_registration_id, booking_id, booking_token, borrower_id, items, kit, requested_for,
                    pickup_from, pickup_until, waitlist_entry_id, canonical_fields):
    """Create one pending request and links; the caller must validate its input.

    Actor and borrower are separately checked against each selected domain.
    A caller must map lock/unique errors only after this transaction rolls back.
    """
    if intent_kind not in {"self", "staff"} or (intent_kind == "staff" and
                                                not (event_registration_id or booking_id)):
        raise Http404
    if intent_kind == "self" and (borrower is None or actor.pk != borrower.pk):
        raise Http404
    with transaction.atomic():
        assert_write_allowed(makerspace_id)
        assert_mapped_write_allowed(makerspace_id)
        if not actor or not getattr(actor, "is_authenticated", False) or not actor.pk:
            raise Http404
        # Refresh the existing instance to preserve authentication restrictions
        # attached by its request context while discarding stale model fields.
        try:
            actor.refresh_from_db()
        except User.DoesNotExist:
            raise Http404 from None
        if (not actor.is_active or actor.access_status != "active" or actor.is_tenant_dump_stub
                or actor.deletion_requested_at or actor.must_change_password
                or not (is_person(actor) or (is_platform(actor) and actor.is_superuser))):
            raise Http404
        # Observe immutable intent before domain locks; revalidate the exact
        # receipt after obtaining the maker lock. Never expose observed IDs.
        observed = EquipmentProposalReceipt.objects.filter(
            makerspace_id=makerspace_id, operation_id=operation_id,
        ).first()
        old_intent = None
        observed_identity = None
        if observed is not None:
            if observed.imported_nonreplayable:
                raise Http404
            try:
                old_intent = json.loads(observed.intent_snapshot)
                canonical_intent_json(old_intent)
                if (old_intent["makerspace_id"] != makerspace_id
                        or old_intent["operation_id"] != str(operation_id)
                        or old_intent["original_borrower_id"] != observed.borrower_id
                        or old_intent["original_creator_id"] != observed.creator_id
                        or old_intent["outcome_kind"] != observed.outcome_kind
                        or not receipt_matches(observed, proposal_fingerprint_from_snapshot(old_intent))):
                    raise ValueError("Receipt mismatch")
            except (ValueError, TypeError, ValidationError):
                raise Http404 from None
            observed_identity = (observed.pk, observed.payload_sha256, observed.borrower_id, observed.creator_id)
        if intent_kind == "self" and booking_token is not None:
            # Body token is resolved only after the nonreplayable pre-observation.
            candidate_maker = Makerspace.objects.filter(pk=makerspace_id).first()
            if candidate_maker is None:
                raise Http404
            booking_id = bridge.member_booking_id(
                candidate_maker, actor, booking_token,
            )
        old_registration_id = old_intent["event_registration_id"] if old_intent else None
        old_booking_id = old_intent["booking_id"] if old_intent else None
        registration_ids = sorted({x for x in (event_registration_id, old_registration_id) if x is not None})
        booking_ids = sorted({x for x in (booking_id, old_booking_id) if x is not None})
        event_for = {x: bridge.observe_event(makerspace_id, x) for x in registration_ids}
        space_for = {x: bridge.observe_booking(makerspace_id, x) for x in booking_ids}
        events = {x: bridge.lock_event(makerspace_id, x) for x in sorted(set(event_for.values()))}
        spaces = {x: bridge.lock_space(makerspace_id, x) for x in sorted(set(space_for.values()))}
        event = events[event_for[event_registration_id]] if event_registration_id is not None else None
        space = spaces[space_for[booking_id]] if booking_id is not None else None
        registration = booking = None
        maker = Makerspace.objects.select_for_update(nowait=True, no_key=True, of=("self",)).filter(
            pk=makerspace_id,
        ).first()
        if maker is None:
            raise Http404
        if intent_kind == "self":
            if not maker.public_site_enabled or not maker.public_inventory_enabled:
                raise Http404
            require_module_for_servable(maker, "public_inventory")
        if registration_ids:
            require_module_locked(maker, "events")
        if booking_ids:
            require_module_locked(maker, "bookings")
        registrations = {x: bridge.lock_registration(events[event_for[x]], x) for x in registration_ids}
        bookings = {x: bridge.lock_booking(spaces[space_for[x]], x) for x in booking_ids}
        registration = registrations.get(event_registration_id)
        booking = bookings.get(booking_id)
        if intent_kind == "staff":
            # Only a member attached to an authorized exact source may be proposed
            # for. A supplied identity is a consistency check, never discovery.
            source_members = [row.member_id for row in (registration, booking) if row is not None]
            if not source_members or any(member is None for member in source_members):
                raise Http404
            try:
                source_borrower = borrower_survivor(User.objects.get(pk=source_members[0]))
                aliases = _aliases(source_borrower)
            except (User.DoesNotExist, ValueError, RuntimeError):
                raise Http404 from None
            if any(member not in aliases for member in source_members):
                raise Http404
            if borrower_id is not None and borrower_id not in aliases:
                raise Http404
            borrower = source_borrower
        try:
            borrower = lock_obligation_owner(borrower, nowait=True)
        except User.DoesNotExist:
            raise Http404 from None
        if module_enabled(maker, "membership"):
            admit_borrower(maker, borrower, planning=True)
        else:
            require_active_account(borrower, maker)
        if registration is not None:
            bridge.validate_event(event, registration, maker, borrower, actor if intent_kind == "staff" else None)
        if booking is not None:
            bridge.validate_booking(space, booking, maker, borrower, actor if intent_kind == "staff" else None)
        if old_registration_id is not None:
            bridge.validate_event(events[event_for[old_registration_id]], registrations[old_registration_id],
                                  maker, borrower, actor if intent_kind == "staff" else None)
        if old_booking_id is not None:
            bridge.validate_booking(spaces[space_for[old_booking_id]], bookings[old_booking_id],
                                    maker, borrower, actor if intent_kind == "staff" else None)
        kit_version = None
        kit_lines = None
        outcome_kind = "request"
        if kit is not None:
            template = EquipmentKitTemplate.objects.select_for_update(nowait=True, of=("self",)).filter(
                pk=kit["id"], makerspace=maker, published_for_contexts=True, archived=False,
            ).first()
            if template is None:
                raise Http404
            kit_version = EquipmentKitVersion.objects.select_for_update(nowait=True, of=("self",)).filter(
                template=template, version=kit["version"],
            ).first()
            if kit_version is None:
                raise Http404
            if not isinstance(kit_version.lines, list) or any(
                not isinstance(line, dict) or type(line.get("product_id")) is not int
                or not 0 < line["product_id"] <= 9007199254740991 for line in kit_version.lines
            ):
                raise Http404
            ids = [line["product_id"] for line in kit_version.lines]
            product_rows = {p.pk: p for p in InventoryProduct.objects.select_for_update(nowait=True, of=("self",))
                            .filter(makerspace=maker, pk__in=ids).order_by("pk")}
            from apps.makerspaces.platform import feature_enabled
            if not public_safe(kit_version.lines, product_rows, maker.pk,
                               consumables_enabled=feature_enabled(maker, "inventory.consumables"),
                               returnable_allowed=lambda product: not product.is_consumable):
                raise Http404
            kit_lines = kit_version.lines
            items = [{"product_id": line["product_id"], "quantity": line["quantity_per_person"]}
                     for line in kit_lines if line["kind"] == "returnable"]
            if not items:
                outcome_kind = "consumable_plan"
        if outcome_kind == "request":
            require_module_locked(maker, "request_workflow")
            require_feature(maker, "loans.enabled")
        else:
            require_feature(maker, "inventory.consumables")
        receipt = locked_receipt(makerspace_id=maker.pk, operation_id=operation_id)
        current_identity = (receipt.pk, receipt.payload_sha256, receipt.borrower_id, receipt.creator_id) if receipt else None
        if (current_identity != observed_identity or
                (receipt is not None and (receipt.imported_nonreplayable
                                          or receipt.intent_snapshot != observed.intent_snapshot))):
            raise ProposalConflict("lock_busy")
        original = receipt.borrower_id if receipt else borrower.pk
        if receipt and original not in _aliases(borrower):
            raise Http404
        if receipt and receipt.creator_id not in _aliases(actor):
            raise Http404
        intent_snapshot = make_proposal_intent(
            makerspace_id=maker.pk, operation_id=operation_id, original_borrower_id=original,
            original_creator_id=receipt.creator_id if receipt else actor.pk,
            intent_kind=intent_kind, outcome_kind=outcome_kind, event_registration_id=event_registration_id,
            booking_id=booking.pk if booking else None, request_fields=canonical_fields,
        )
        digest = proposal_fingerprint_from_snapshot(intent_snapshot)
        if receipt:
            _require_same_outcome(receipt, outcome_kind)
            if not receipt_matches(receipt, digest):
                raise ProposalConflict("operation_conflict")
            if outcome_kind == "consumable_plan":
                plan = receipt.consumable_plan
                if (not plan or plan.makerspace_id != maker.pk
                        or plan.borrower_id not in _aliases(borrower)):
                    raise Http404
                if registration is not None:
                    if not bridge.context_exists("events", maker=maker, result=plan, target=event,
                                                 participant=registration, plan=True):
                        raise Http404
                if booking is not None:
                    if not bridge.context_exists("bookings", maker=maker, result=plan, target=booking, plan=True):
                        raise Http404
                return "consumable_plan", plan, True
            if (not receipt.request_id or receipt.request.makerspace_id != maker.pk
                    or receipt.request.requester_id not in _aliases(borrower)):
                raise Http404
            if registration is not None:
                if not bridge.context_exists("events", maker=maker, result=receipt.request, target=event,
                                             participant=registration):
                    raise Http404
            if booking is not None:
                if not bridge.context_exists("bookings", maker=maker, result=receipt.request, target=booking):
                    raise Http404
            return "request", receipt.request, True
        if outcome_kind == "consumable_plan":
            from apps.inventory.equipment_plan_service import create_plan_locked
            plan = create_plan_locked(makerspace=maker, borrower=borrower, actor=actor,
                                      kit_id=kit["id"], version_number=kit["version"])
            if registration is not None:
                bridge.attach_context("events", maker=maker, result=plan, target=event,
                                      participant=registration, actor=actor, plan=True)
            if booking is not None:
                bridge.attach_context("bookings", maker=maker, result=plan, target=booking, actor=actor, plan=True)
            create_receipt(makerspace_id=maker.pk, operation_id=operation_id, borrower=borrower, creator=actor,
                           snapshot=intent_snapshot, plan=plan)
            return "consumable_plan", plan, False
        products = {p.pk: p for p in InventoryProduct.objects.filter(
            makerspace=maker, pk__in=[item["product_id"] for item in items],
            is_public=True, is_archived=False, is_consumable=False,
        )}
        if len(products) != len(items):
            raise Http404
        if registration is None:
            refuse_event_only(products.values())  # decision 221b: a booking is not an event
        contact_snapshot = RequesterSnapshot(username=borrower.username, name=borrower.display_name,
                                             email=borrower.email, phone=borrower.phone)
        req = submit_locked(maker, [{"product": products[i["product_id"]], "quantity": i["quantity"]}
                                    for i in items], requested_for, requester_principal=borrower,
                            contact_snapshot=contact_snapshot, audit_actor=actor, account_less_marker="",
                            contact_key="", pickup_from=pickup_from, pickup_until=pickup_until,
                            waitlist_entry_id=waitlist_entry_id)
        if kit_version is not None:
            EquipmentKitAllocation.objects.create(
                makerspace=maker, request=req, kit_version=kit_version, lines=kit_lines,
            )
        if registration is not None:
            bridge.attach_context("events", maker=maker, result=req, target=event, participant=registration, actor=actor)
        if booking is not None:
            bridge.attach_context("bookings", maker=maker, result=req, target=booking, actor=actor)
        create_receipt(makerspace_id=maker.pk, operation_id=operation_id, borrower=borrower, creator=actor,
                       snapshot=intent_snapshot, request=req)
        return "request", req, False
