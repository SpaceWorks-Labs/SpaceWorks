"""Construct final INSERTs; only allowlisted mutable page draft pointers get fixups."""

from django.apps import apps

from apps.encryption.registry import fields_for

from .archive_stream import database_value
from .closure_references import (
    CROSS_TENANT_DEPENDENT_REFERENCES,
    MOVABLE_ROW_REFERENCES,
    MissingReferenceDisposition,
)
from .event_hashes import event_registration_hash_columns
from .identity_resolution import decision_for_source_user
from .omitted_fields import OMITTED_FIELD_RECONSTRUCTIONS, OmittedFieldDisposition
from .object_fields import rewrite_object_fields
from .pii_reencryption import reencrypt_mapped_value_with_plaintext
from .insertion_errors import PrimaryKeyMapUnavailable
from .row_dispositions import row_disposition, _seeded_target_pk
from .semantic_remap import remap_semantic_references
from .row_conditions import condition_matches
from .target_projection import (
    FK_POLICIES,
    SEEDED_RESOLUTIONS,
    TARGET_FIELD_PROJECTION,
    ReferenceDisposition,
)
from .unique_values import collision_policy


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
    if not _remap_foreign_keys(model, source, row, job, pk_map, target, references):
        return None
    if label == "events.EventSession" and "identity_id" not in source:
        from .public_page_legacy import identity_for_legacy_session
        row["identity_id"] = identity_for_legacy_session(row, references.archive)
    _clear_walk_in_waiver_evidence(label, source, row, job)
    if not remap_semantic_references(label, source, row, pk_map, references):
        return None
    from .public_page_document_remap import remap_documents
    remap_documents(label, row, pk_map)

    for mapped in fields_for(model):
        column = model._meta.get_field(mapped.field_name).column
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
    model.objects.filter(pk=target_pk).update(**values)
    return True


def _reconstructed_value(label, field, fresh_values):
    disposition = OMITTED_FIELD_RECONSTRUCTIONS[(label, field.name)]
    if label in {"events.SubmissionAsset", "events.HackathonParticipantAsset"} and field.name in {"staging_key", "verification_key"}:
        return _fresh_unique(field, fresh_values)
    if disposition is OmittedFieldDisposition.FRESH:
        value = _fresh_unique(field, fresh_values)
    elif disposition is OmittedFieldDisposition.EMPTY_STRING:
        value = ""
    elif disposition is OmittedFieldDisposition.NULL:
        value = None
    elif disposition is OmittedFieldDisposition.DERIVED:
        value = field.get_default() if field.has_default() else None
    elif disposition is OmittedFieldDisposition.DROP_ROW:
        value = ""
    else:
        raise ValueError(f"Unsupported omitted-field disposition for {label}.{field.name}.")
    return value


def _fresh_unique(field, fresh_values, generator=None):
    key = (field.model._meta.label, field.name)
    current_batch = fresh_values.setdefault(key, set())
    if field.model._meta.label in {"events.SubmissionAsset", "events.HackathonParticipantAsset"} and field.name in {"staging_key", "verification_key"}:
        from uuid import uuid4
        generate = lambda: f"import-coordination/{uuid4()}/{field.name}"
    else:
        generate = generator or field.get_default
    for _attempt in range(16):
        value = generate()
        if value in current_batch:
            continue
        if field.model._base_manager.filter(**{field.name: value}).exists():
            continue
        current_batch.add(value)
        return value
    raise RuntimeError(f"Could not generate a unique value for {key[0]}.{key[1]}.")


def protect_carried_unique_values(model, row, target, fresh_values):
    """Preserve carried labels/keys, changing only a value that actually collides."""
    outcomes = []
    label = model._meta.label
    for field in model._meta.local_concrete_fields:
        policy = collision_policy(label, field.name)
        if policy is None:
            continue
        value = row[field.column]
        if value is None:
            # NULL never violates a unique constraint; there is no identity to preserve.
            continue
        key = (label, field.name)
        current_batch = fresh_values.setdefault(key, set())
        collision = value in current_batch or model._base_manager.filter(
            **{field.name: value}
        ).exists()
        if collision:
            generator = (
                (lambda: policy.generator(row, target, value))
                if policy.generator is not None
                else field.get_default
            )
            row[field.column] = _fresh_unique(field, fresh_values, generator)
            outcomes.append((field.name, "regenerated"))
        else:
            current_batch.add(value)
            outcomes.append((field.name, "preserved"))
    return outcomes


def _apply_target_fields(label, source, row):
    for (model_label, name), policy in TARGET_FIELD_PROJECTION.items():
        if model_label != label:
            continue
        if not condition_matches(policy.condition, source):
            continue
        field = apps.get_model(label)._meta.get_field(name)
        row[field.column] = policy.resolved_value(label, name)


def _remap_foreign_keys(model, source, row, job, pk_map, target, references):
    from .portable_staff import apply_staff_role
    staff = apply_staff_role(model, source, row, target)
    for field in model._meta.local_concrete_fields:
        if not field.is_relation or field.related_model is None:
            continue
        source_value = row[field.column]
        if source_value is None:
            continue
        edge_policy = FK_POLICIES.get((model._meta.label, field.name))
        if staff and (model._meta.label, field.name) in {
            ("makerspaces.MakerspaceMembership", "assigned_role"),
            ("makerspaces.MembershipAdditionalRole", "role"),
        }:
            continue
        if staff and model._meta.label == "machines.MembershipMachineTypeScope":
            edge_policy = None
        if edge_policy and edge_policy.disposition is ReferenceDisposition.DROP_ROW:
            return False
        if edge_policy and edge_policy.disposition is ReferenceDisposition.REMAP_TARGET_MEMBER:
            row[field.column] = target.roles.get(slug="member").pk
            continue
        if field.related_model._meta.label == "accounts.User":
            row[field.column] = pk_map.lookup(field.related_model, source_value)
        elif field.related_model._meta.label == "encryption.SearchKeyGeneration":
            continue
        elif field.related_model._meta.label == "accounts.MemberClaimCode":
            row[field.column] = None
        else:
            try:
                row[field.column] = pk_map.lookup(field.related_model, source_value)
            except PrimaryKeyMapUnavailable:
                if field.name == "profile" and model._meta.label in {
                    "makerspaces.MakerspacePublicPageRevisionMember", "events.EventPageRevisionMember",
                }:
                    row[field.column] = None
                    continue
                # A crafted archive may retain the numeric id beside its snapshot.
                # Only a declared NULL disposition authorizes turning that id inert.
                if field.null and _null_with_provenance(
                    model._meta.label, field.name, source, references
                ):
                    row[field.column] = None
                else:
                    raise
    return True


def _null_with_provenance(label, field_name, source, references):
    rule = MOVABLE_ROW_REFERENCES.get((label, field_name))
    if rule is not None:
        disposition = rule.disposition
    else:
        disposition = CROSS_TENANT_DEPENDENT_REFERENCES.get((label, field_name))
    return (
        disposition is MissingReferenceDisposition.NULL_WITH_PROVENANCE
        and references.get(label, source["id"], field_name) is not None
    )


def _clear_walk_in_waiver_evidence(label, source, row, job):
    if label != "makerspaces.MakerspaceMembership":
        return
    decision = decision_for_source_user(job, source["user_id"])
    if decision.identity_resolution != decision.IdentityResolution.CREATE_WALK_IN:
        return
    for name in (
        "waiver_accepted_at", "waiver_version_accepted", "accepted_waiver",
        "witnessed_waiver", "witnessed_waiver_version", "witnessed_by",
        "witnessed_actor_snapshot", "witnessed_at",
    ):
        field = apps.get_model(label)._meta.get_field(name)
        row[field.column] = None
