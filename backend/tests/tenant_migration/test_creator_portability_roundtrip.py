"""Full portable receipt round-trip; source candidate, not yet executed."""
from uuid import uuid4
import pytest
from django.db import transaction
from apps.encryption.tenant_preparation import prepare_tenant_key, tenant_key_context
from apps.hardware_requests.contextual_equipment_service import create_pending
from apps.inventory.equipment_proposal_receipts import create_receipt, make_proposal_intent
from apps.inventory.models_equipment_proposals import EquipmentProposalReceipt
from apps.makerspaces.models import Makerspace
from apps.tenant_migration.materialization import materialize_tenant
from apps.tenant_migration import cutover
from tests.tenant_migration.object_helpers import pairing_and_receipt
from tests.tenant_migration.protocol_helpers import superadmin
from tests.data_export.portable_helpers import make_space, make_user
from tests.encryption.conftest import enabled_encryption
from tests.return_helpers import make_product
from tests.tenant_migration.materialization_helpers import portable_import_case




def activate(case, target):
    actor = superadmin("equipment-activate-" + str(target.pk))
    pairing, envelope = pairing_and_receipt(case.job, actor)
    cutover.activate_target(pairing=pairing, import_job=case.job, receipt_envelope=envelope, actor=actor)
    target.refresh_from_db()
    assert target.lifecycle_state == Makerspace.LifecycleState.ACTIVE
    target.public_site_enabled = True
    target.public_inventory_enabled = True
    target.enabled_features = sorted(set(target.enabled_features or []) | {"loans.enabled"})
    target.save(update_fields=["public_site_enabled", "public_inventory_enabled", "enabled_features"])
    from apps.makerspaces.guards import require_module_for_servable, require_module, require_feature
    require_module_for_servable(target, "public_inventory")
    require_module(target, "request_workflow")
    require_feature(target, "loans.enabled")

@pytest.mark.django_db(transaction=True)
def test_link_existing_creator_receipt_import_and_authorized_replay():
    with enabled_encryption():
        source_actor = make_user("equipment-origin")
        target_actor = make_user("equipment-target")
        space = make_space("equipment-origin")
        operation = uuid4()
        def seed(maker, actor, request):
            product = make_product(maker, is_public=True)
            fields = {"items": [{"product_id": product.pk, "quantity": 1}], "requested_for": "workshop"}
            snapshot = make_proposal_intent(makerspace_id=maker.pk, operation_id=operation,
                original_borrower_id=actor.pk, original_creator_id=actor.pk, intent_kind="self",
                outcome_kind="request", event_registration_id=None, booking_id=None, request_fields=fields)
            with tenant_key_context(prepare_tenant_key(maker.pk)), transaction.atomic():
                create_receipt(makerspace_id=maker.pk, operation_id=operation, borrower=actor,
                               creator=actor, snapshot=snapshot, request=request)
            return product.pk
        with portable_import_case(space, source_actor, prepare_source=seed) as case:
            case.decide_link(source_actor, target_actor)
            result = materialize_tenant(case.root, case.job, case.carried,
                                        target_identity={"slug": "equipment-target"})
            target = Makerspace.objects.get(pk=result.target_makerspace_id)
            activate(case, target)
            receipt = EquipmentProposalReceipt.objects.get(makerspace=target, operation_id=operation)
            assert receipt.creator_id == target_actor.pk and receipt.borrower_id == target_actor.pk
            assert not receipt.imported_nonreplayable
            # Imported snapshots hold mapped product IDs; the original UUID and
            # normalized content must resolve to the existing request, not a new one.
            import json
            intent = json.loads(receipt.intent_snapshot)
            fields = {"items": [{"product_id": intent["product_ids"][0], "quantity": 1}], "requested_for": "workshop"}
            kind, request, replayed = create_pending(makerspace_id=target.pk, actor=target_actor,
                borrower=target_actor, intent_kind="self", operation_id=operation, event_registration_id=None,
                booking_id=None, booking_token=None, borrower_id=None, items=fields["items"], kit=None,
                requested_for="workshop", pickup_from=None, pickup_until=None, waitlist_entry_id=None,
                canonical_fields=fields)
            assert (kind, request.pk, replayed) == ("request", receipt.request_id, True)


@pytest.mark.django_db(transaction=True)
def test_merged_creator_shell_import_replays_for_authorized_survivor():
    from tests.tenant_migration.test_person_portability import _merge
    with enabled_encryption():
        survivor = make_user("equipment-shell-survivor")
        target_actor = make_user("equipment-shell-target")
        maker = make_space("equipment-shell-origin")
        operation = uuid4()
        state = {}
        def seed(space, borrower, request):
            shell = make_user("equipment-shell-original")
            product = make_product(space, is_public=True)
            fields = {"items": [{"product_id": product.pk, "quantity": 1}], "requested_for": "workshop"}
            snapshot = make_proposal_intent(makerspace_id=space.pk, operation_id=operation,
                original_borrower_id=borrower.pk, original_creator_id=shell.pk, intent_kind="self",
                outcome_kind="request", event_registration_id=None, booking_id=None, request_fields=fields)
            with tenant_key_context(prepare_tenant_key(space.pk)), transaction.atomic():
                create_receipt(makerspace_id=space.pk, operation_id=operation, borrower=borrower,
                               creator=shell, snapshot=snapshot, request=request)
            _merge(shell, borrower)
            state["shell"] = shell
        with portable_import_case(maker, survivor, prepare_source=seed) as case:
            case.decide_link(survivor, target_actor)
            case.decide_walk_in(state["shell"])
            result = materialize_tenant(case.root, case.job, case.carried, target_identity={"slug": "equipment-shell-target"})
            target = Makerspace.objects.get(pk=result.target_makerspace_id)
            activate(case, target)
            receipt = EquipmentProposalReceipt.objects.get(makerspace=target, operation_id=operation)
            assert receipt.creator.merged_into_id == target_actor.pk
            assert receipt.borrower_id == target_actor.pk and not receipt.imported_nonreplayable
            import json
            intent = json.loads(receipt.intent_snapshot)
            fields = {"items": [{"product_id": intent["product_ids"][0], "quantity": 1}], "requested_for": "workshop"}
            kind, request, replayed = create_pending(makerspace_id=target.pk, actor=target_actor, borrower=target_actor,
                intent_kind="self", operation_id=operation, event_registration_id=None, booking_id=None,
                booking_token=None, borrower_id=None, items=fields["items"], kit=None, requested_for="workshop",
                pickup_from=None, pickup_until=None, waitlist_entry_id=None, canonical_fields=fields)
            assert (kind, request.pk, replayed) == ("request", receipt.request_id, True)


@pytest.mark.django_db(transaction=True)
def test_unmapped_optional_creator_is_sticky_even_when_source_numeric_user_exists(monkeypatch):
    import json
    from django.http import Http404
    from apps.accounts.models import User
    with enabled_encryption():
        borrower = make_user("equipment-missing-creator-borrower")
        target_actor = make_user("equipment-missing-creator-target")
        maker = make_space("equipment-missing-creator")
        operation = uuid4()
        state = {}
        def seed(space, actor, request):
            creator = make_user("equipment-optional-creator")
            product = make_product(space, is_public=True)
            fields = {"items": [{"product_id": product.pk, "quantity": 1}], "requested_for": "workshop"}
            intent = make_proposal_intent(makerspace_id=space.pk, operation_id=operation,
                original_borrower_id=actor.pk, original_creator_id=creator.pk, intent_kind="self",
                outcome_kind="request", event_registration_id=None, booking_id=None, request_fields=fields)
            with tenant_key_context(prepare_tenant_key(space.pk)), transaction.atomic():
                create_receipt(makerspace_id=space.pk, operation_id=operation, borrower=actor,
                               creator=creator, snapshot=intent, request=request)
            state["creator"] = creator
        with portable_import_case(maker, borrower, prepare_source=seed) as case:
            case.decide_link(borrower, target_actor)
            # Deliberately no decision for the optional historical creator. The
            # source PK still exists locally, simulating a coincident target ID.
            assert User.objects.filter(pk=state["creator"].pk).exists()
            from apps.tenant_migration import materialization
            original_reserve = materialization.preallocate_walk_in_ids
            def reserve_collision(job, pk_map, required):
                original_reserve(job, pk_map, required)
                pk_map.add_many(User, [(state["creator"].pk, state["creator"].pk)])
            monkeypatch.setattr(materialization, "preallocate_walk_in_ids", reserve_collision)
            result = materialize_tenant(case.root, case.job, case.carried,
                                        target_identity={"slug": "equipment-missing-target"})
            target = Makerspace.objects.get(pk=result.target_makerspace_id)
            activate(case, target)
            receipt = EquipmentProposalReceipt.objects.get(makerspace=target, operation_id=operation)
            assert receipt.creator_id is None and receipt.borrower_id == target_actor.pk
            assert receipt.imported_nonreplayable and receipt.payload_sha256 == "0" * 64
            assert json.loads(receipt.intent_snapshot) == {"version": 2, "outcome_kind": "request", "unavailable": True}
            with pytest.raises(Http404):
                create_pending(makerspace_id=target.pk, actor=target_actor, borrower=target_actor,
                    intent_kind="self", operation_id=operation, event_registration_id=None, booking_id=None,
                    booking_token=None, borrower_id=None, items=[], kit=None, requested_for="workshop",
                    pickup_from=None, pickup_until=None, waitlist_entry_id=None, canonical_fields={})
