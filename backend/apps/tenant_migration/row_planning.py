"""Construct final INSERTs; only allowlisted mutable page draft pointers get fixups."""

from django.apps import apps

from apps.encryption.registry import fields_for

from .archive_stream import database_value
from .event_hashes import event_registration_hash_columns
from .identity_resolution import decision_for_source_user
from .object_fields import rewrite_object_fields
from .pii_reencryption import reencrypt_mapped_value_with_plaintext
from .row_dispositions import row_disposition, _seeded_target_pk
from .semantic_remap import remap_semantic_references
from .row_conditions import condition_matches
from .row_references import (
    _clear_walk_in_waiver_evidence,
    _null_with_provenance,
    _remap_foreign_keys,
)
from .row_values import _fresh_unique, _reconstructed_value, protect_carried_unique_values
from .target_projection import SEEDED_RESOLUTIONS, TARGET_FIELD_PROJECTION
from apps.backup.capture_managers import every_row


def final_row(
    model,
    source,
    *,
    job,
    pk_map,
    references,
    target,
    deks,
    fresh_values,
    object_key_map,
):
    label = model._meta.label
    disposition = row_disposition(label, source, references)
    if disposition in {"drop", "resolve"}:
        return None
    if _seeded_target_pk(label, source, target) is not None:
        return None
    if label == "makerspaces.MakerspaceMembership":
        decision = decision_for_source_user(job, source["user_id"])
        if decision.membership_disposition == decision.MembershipDisposition.NO_MEMBERSHIP:
            return None

    row = {}
    plaintext = {}
    for field in model._meta.local_concrete_fields:
        if field.primary_key:
            value = pk_map.lookup(model, source[field.attname])
        elif field.attname in source:
            value = database_value(field, source[field.attname])
        else:
            from .public_page_legacy import reconstructed_field
            reconstructed, value = reconstructed_field(label, field)
            if not reconstructed:
                value = _reconstructed_value(label, field, fresh_values)
        row[field.column] = value

    _apply_target_fields(label, source, row)
    from .page_pointer_fixups import deferred_pointer
    for field in model._meta.local_concrete_fields:
        if deferred_pointer(field):
            row[field.column] = None
    if label in {"events.SubmissionAsset", "events.HackathonParticipantAsset"}:
        from apps.events.submissions.portability import asset_import_values
        row = asset_import_values(row)
        if source["state"] not in {"ready", "expired"}:
            # Pending source bytes do not travel. Preserve inert metadata under
            # a fresh target locator, never a source multipart/final key.
            from uuid import uuid4
            object_key_map = {**object_key_map, source["object_key"]: f"import-coordination/{uuid4()}/final"}
    if label in {"events.StageFormAsset", "payments.FinanceAttachment"}:
        from .reimbursement_assets_import import asset_import_row
        row, object_key_map = asset_import_row(label, source, row, object_key_map)
    rewrite_object_fields(model, row, object_key_map)
    creator_unavailable = False
    if label in {"inventory.EquipmentProposalReceipt", "inventory.EquipmentConsumableUseReceipt"}:
        from .equipment_intent_preinsert import prepare_receipt_creator
        creator_unavailable = prepare_receipt_creator(row, pk_map, references)
    decision_sticky = False
    if label == "events.EventBookingDecision":
        from .booking_decision_import import prepare
        decision_sticky = prepare(row, job=job, pk_map=pk_map, references=references, target=target)
    if not _remap_foreign_keys(model, source, row, job, pk_map, target, references):
        return None
    if label == "events.EventSession" and "identity_id" not in source:
        from .public_page_legacy import identity_for_legacy_session
        row["identity_id"] = identity_for_legacy_session(row, references.archive)
    _clear_walk_in_waiver_evidence(label, source, row, job)
    if not remap_semantic_references(label, source, row, pk_map, references):
        return None
    if label == "events.EventBookingDecision":
        from .booking_decision_import import finish
        finish(row, decision_sticky)
    from .public_page_document_remap import remap_documents
    remap_documents(label, row, pk_map)

    for mapped in fields_for(model):
        column = model._meta.get_field(mapped.field_name).column
        if label in {"inventory.EquipmentProposalReceipt", "inventory.EquipmentConsumableUseReceipt"} and mapped.field_name == "intent_snapshot":
            from .equipment_intent_preinsert import rebind_receipt_before_insert
            row[column], row["payload_sha256"], row["imported_nonreplayable"] = rebind_receipt_before_insert(
                model, row[column], source=source, row=row, job=job, target=target, deks=deks, pk_map=pk_map, references=references, creator_unavailable=creator_unavailable)
            continue
        source_aad = {
            "makerspace_id": int(job.source_makerspace_id),
            "table": model._meta.db_table,
            "pk": source[model._meta.pk.attname],
            "field": mapped.field_name,
        }
        from .pii_events_programme import rebind_programme_document
        transformed = rebind_programme_document(model, mapped.field_name, row[column], source=source, row=row,
            source_id=int(job.source_makerspace_id), target_id=target.pk, deks=deks,
            map_id=lambda label, value: pk_map.lookup(apps.get_model(label), value))
        if transformed is None:
            from .pii_reimbursements import rebind_reimbursement_document
            transformed = rebind_reimbursement_document(model, mapped.field_name, row[column], source=source,
                row=row, source_id=int(job.source_makerspace_id), target_id=target.pk, deks=deks,
                map_id=lambda label, value: pk_map.lookup(apps.get_model(label), value))
        row[column], raw_plaintext = transformed if transformed is not None else reencrypt_mapped_value_with_plaintext(
            row[column],
            source_aad=source_aad,
            target_makerspace_id=target.pk,
            target_table=model._meta.db_table,
            target_pk=row[model._meta.pk.column],
            target_field=mapped.field_name,
            deks=deks,
        )
        plaintext[mapped.field_name] = (
            raw_plaintext.decode("utf-8")
            if isinstance(raw_plaintext, bytes)
            else raw_plaintext
        )
    if label == "machines.MachineServiceRequest":
        mark_imported_head(model, row)
    from .pii_events_programme import rebind_derivation_history
    rebind_derivation_history(model, source, row, source_makerspace_id=int(job.source_makerspace_id),
        target_makerspace_id=target.pk, deks=deks)
    if label == "events.EventRegistration":
        row.update(
            event_registration_hash_columns(
                plaintext.get("email", ""),
                target_makerspace_id=target.pk,
                target_event_id=row[model._meta.get_field("event").column],
            )
        )
    if label == "makerspaces.PublicHandle":
        from .catalog_profiles import prepare_import_handle
        if not prepare_import_handle(row, fresh_values):
            if not hasattr(references, "public_page_warnings"):
                references.public_page_warnings = []
            references.public_page_warnings.append({"code": "handle_dropped", "source_id": source["id"]})
            return None
    return row


def mark_imported_head(model, row):
    """C11: notification envelopes never travel and imported jobs get new ids, so a job
    that arrives ACCEPTED is treated as already told it is next (no ``next`` on import).
    Started/completed/cancelled markers travel as data and suppress their replays."""
    flag = model._meta.get_field("imported_head_notified").column
    status = model._meta.get_field("status").column
    row[flag] = bool(row.get(flag)) or row.get(status) == "accepted"


def update_resolved_row(model, source, target):
    resolution = SEEDED_RESOLUTIONS.get(model._meta.label)
    target_pk = _seeded_target_pk(model._meta.label, source, target)
    if resolution is None or target_pk is None or not resolution.archive_update_fields:
        return False
    values = {
        model._meta.get_field(name).attname: database_value(
            model._meta.get_field(name), source[model._meta.get_field(name).attname]
        )
        for name in resolution.archive_update_fields
    }
    every_row(model).filter(pk=target_pk).update(**values)
    return True


def _apply_target_fields(label, source, row):
    for (model_label, name), policy in TARGET_FIELD_PROJECTION.items():
        if model_label != label:
            continue
        if not condition_matches(policy.condition, source):
            continue
        field = apps.get_model(label)._meta.get_field(name)
        row[field.column] = policy.resolved_value(label, name)
