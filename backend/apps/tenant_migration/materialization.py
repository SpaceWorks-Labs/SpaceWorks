"""All-or-nothing database materialization of one decrypted tenant archive."""

from django.apps import apps
from django.db import connection, transaction

from apps.audit.keys import advance_attestation_cutover
from apps.encryption.write_fence import fence_operation

from .archive_stream import PortableArchive
from .blind_indexes import rebuild_blind_indexes
from .dependency_order import exported_models_in_dependency_order
from .external_materialization import materialize_external_references
from .identity_resolution import (
    RequiredIdentitySet,
    preallocate_walk_in_ids,
    resolve_identities,
)
from .import_keys import install_carried_deks
from .import_finalization import finalize_import_job
from .insertion_errors import MaterializationAlreadyCommitted, MaterializationSuperseded
from .materialization_failure import handle_materialization_failure
from .models_import_job import TenantImportJob
from .object_import import (
    prepare_import_objects,
    promote_import_objects,
)
from .pk_maps import TransactionPkMap
from .reference_state import ReferenceState
from .row_dispositions import ImportAccounting, preallocate_model
from .materialization_rows import (
    MaterializationResult,
    _close_target_import_fence,
    _insert_models,
    _report_for,
)
from .target_creation import create_target_makerspace
from .verification import verify_materialization


def materialize_tenant(
    archive_directory,
    job,
    carried_deks,
    *,
    target_identity=None,
    batch_size=500,
    run_attempt=None,
    run_lock=None,
):
    """Commit database state atomically, then promote its staged objects."""
    archive = PortableArchive(archive_directory)
    target = None
    locked_job = None
    object_plan = None
    carried = tuple(carried_deks)
    if batch_size < 1:
        raise ValueError("batch_size must be positive.")
    try:
        object_plan = prepare_import_objects(archive, job)
        with transaction.atomic():
            locked_job = TenantImportJob.objects.select_for_update().get(pk=job.pk)
            if run_attempt is not None and (
                locked_job.run_attempt != run_attempt
                or locked_job.status != TenantImportJob.Status.MATERIALIZING
            ):
                raise MaterializationSuperseded("A replacement owns this import execution.")
            if locked_job.target_makerspace_id is not None:
                raise MaterializationAlreadyCommitted(
                    "The import database materialization is already committed."
                )
            target = create_target_makerspace(
                archive,
                locked_job,
                target_identity=target_identity,
                object_key_map=object_plan.target_keys,
            )
            locked_job.target_makerspace = target
            locked_job.status = TenantImportJob.Status.MATERIALIZING
            locked_job.save(
                update_fields=("target_makerspace", "status", "updated_at")
            )
            _close_target_import_fence(target, locked_job.pk)

            with fence_operation(locked_job.pk):
                # Django's PostgreSQL FKs are transaction-deferred. This permits a
                # self-FK such as Box.parent to point at a preallocated row inserted
                # later in the same model stream without buffering the hierarchy.
                with connection.cursor() as cursor:
                    cursor.execute("SET CONSTRAINTS ALL DEFERRED")
                references = ReferenceState(archive)
                pk_map = TransactionPkMap()
                accounting = ImportAccounting()
                required_identities = RequiredIdentitySet()
                ordered = exported_models_in_dependency_order(apps)

                for model in ordered:
                    preallocate_model(
                        model,
                        archive,
                        pk_map,
                        references,
                        target,
                        accounting,
                        locked_job,
                        required_identities,
                    )
                preallocate_walk_in_ids(locked_job, pk_map, required_identities)
                deks = {
                    int(record["version"]): record["dek"]
                    for record in carried
                    if record.get("insert_at_target", True) is not False
                }
                # The credential block (C-18) is sealed under these same carried DEKs.
                identities = resolve_identities(
                    archive, locked_job, pk_map, required_identities, deks
                )
                installed_versions = install_carried_deks(target, carried)
                from .semantic_reimbursements import prepare_project_refs, reset_project_refs
                project_refs = prepare_project_refs(archive, pk_map)
                try:
                    regenerated = _insert_models(
                        ordered,
                        archive,
                        locked_job,
                        pk_map,
                        references,
                        target,
                        deks,
                        accounting,
                        batch_size,
                        object_plan.target_keys,
                    )
                finally:
                    reset_project_refs(project_refs)
                from .reimbursement_assets_import import register_imported_assets
                register_imported_assets(target)
                from .page_pointer_fixups import apply_page_pointer_fixups
                page_fixups = apply_page_pointer_fixups(archive, pk_map)
                # Imported audit rows have no target MAC (see
                # advance_attestation_cutover). Move this tenant's attestation cutover
                # past them so verification reports them as unattested history rather
                # than as MACs this deployment stripped.
                advance_attestation_cutover(target.pk)
                external_count = materialize_external_references(
                    archive, locked_job, target, pk_map, batch_size=batch_size
                )
                blind_count = rebuild_blind_indexes(target, batch_size=batch_size)
                verify_materialization(
                    archive=archive,
                    models=ordered,
                    target=target,
                    job=locked_job,
                    pk_map=pk_map,
                    references=references,
                    accounting=accounting,
                    identity_report=identities,
                    regenerated_fields=regenerated,
                )
            result = MaterializationResult(
                target_makerspace_id=target.pk,
                imported=dict(accounting.imported),
                resolved=dict(accounting.resolved),
                dropped=dict(accounting.dropped),
                preserved=dict(accounting.preserved),
                regenerated=dict(accounting.regenerated),
                identities_linked=identities.linked,
                identities_created=identities.created,
                preexisting_global_authority=identities.preexisting_global_authority,
                installed_dek_versions=installed_versions,
                blind_indexes_created=blind_count,
                external_references_created=external_count,
                objects_staged=object_plan.staged,
                object_keys_regenerated=object_plan.regenerated,
                object_key_regenerations=dict(object_plan.regenerated_keys),
                objects_promoted=0,
            )
            locked_job.status = TenantImportJob.Status.FINALIZING
            locked_job.materialization_report = _report_for(result)
            locked_job.materialization_report["public_page_pointer_fixups"] = page_fixups
            locked_job.materialization_report["accounts"] = {
                "shells_created": identities.shells_created, "shells_remapped": identities.shells_remapped,
                "credentials_installed": identities.credentials_installed,
            }
            locked_job.materialization_report["public_page_reconstruction"] = getattr(archive, "public_page_reconstruction", {})
            locked_job.materialization_report["public_page_warnings"] = getattr(references, "public_page_warnings", [])
            locked_job.save(
                update_fields=("status", "materialization_report", "updated_at")
            )
            if run_lock is not None:
                run_lock.require_retained()
        promoted = promote_import_objects(locked_job)
        finalize_import_job(locked_job, actor=locked_job.actor)
        return MaterializationResult(
            **{
                **result.__dict__,
                "objects_promoted": promoted,
            }
        )
    except Exception as exc:
        handle_materialization_failure(
            job=job, target=target, error=exc, run_attempt=run_attempt,
        )
        raise
