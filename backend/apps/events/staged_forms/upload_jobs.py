"""Leased validation with no storage/scanner calls under domain row locks."""
from contextlib import contextmanager, nullcontext
from django.db import transaction
from django.utils import timezone
from apps.events.models import Event, EventSeries
from apps.events.programme_locks import fences, lock_authority
from apps.makerspaces.guards import require_module_locked
from apps.payments.event_payouts.errors import require
from apps.tenant_migration.gate_runtime import boundary_tenant_write
from .definition_models import EventStageForm
from .response_models import StageFormAssignment, StageFormResponse
from .upload_models import StageFormAsset
from .upload_workflow import claim_validation_locked, finish_validation_locked
from .upload_commands import editable
from .file_validation import inspect_file


def scan_options():
    from apps.events.submissions.api_runtime import runtime
    try:
        options = dict(runtime().scan_options)
    except Exception:
        require(False, "scanner_unavailable", status=503)
    require(options.get("backend") in ("none", "clamav"), "scanner_unavailable", status=503)
    return options


@contextmanager
def locked_asset(seed, *, runtime=True):
    event_seed = Event.objects.get(pk=seed.event_id)
    from .transactions import prepared_keys
    keys = prepared_keys(event_seed.makerspace_id) if runtime else nullcontext()
    with boundary_tenant_write(event_seed.makerspace_id), keys, transaction.atomic(), fences(
        tenant_ids=(event_seed.makerspace_id,), account_ids=(seed.owner_member_id,) if runtime else ()):
        if event_seed.series_id:
            EventSeries.objects.select_for_update().get(pk=event_seed.series_id)
        event = Event.objects.select_for_update().get(pk=seed.event_id)
        if runtime:
            event.makerspace = require_module_locked(event.makerspace_id, "events")
            from apps.accounts.models import User
            from apps.accounts.account_kind_guards import require_member_account
            from apps.presence.guard import require_active_principal
            from apps.makerspaces.models import MakerspaceMembership
            actor = lock_authority(User.objects.get(pk=seed.owner_member_id), event)
            require_member_account(actor)
            require_active_principal(actor, event.makerspace)
            require(not MakerspaceMembership.objects.filter(user=actor, makerspace=event.makerspace).exclude(status="active").exists(),
                    "account_restricted", status=403)
        assignment_seed = StageFormAssignment.objects.get(pk=seed.assignment_id)
        EventStageForm.objects.select_for_update().get(pk=assignment_seed.stage_form_id)
        assignment = StageFormAssignment.objects.select_for_update().get(pk=seed.assignment_id)
        StageFormResponse.objects.select_for_update().get(assignment=assignment)
        asset = StageFormAsset.objects.select_for_update().get(pk=seed.pk)
        asset.event, asset.assignment = event, assignment
        yield asset


def validate_asset(asset_id, *, store=None):
    seed = StageFormAsset.objects.select_related("event").get(pk=asset_id)
    # The source lock-only boundary spans scanner/storage I/O; the event and
    # account transactions below remain short and never include those calls.
    with boundary_tenant_write(seed.event.makerspace_id):
        return _validate_asset(seed, store=store)


def _validate_asset(seed, *, store=None):
    from apps.accounts.models import User
    from apps.events.submissions.scanning import scan
    from .storage import storage, ScanReader
    actor = User.objects.get(pk=seed.owner_member_id)
    with locked_asset(seed) as asset:
        editable(asset.assignment, actor=actor)
        require(asset.expires_at is None or timezone.now() < asset.expires_at, "stage_file_expired", status=410)
        token = claim_validation_locked(asset, now=timezone.now())
    result, error = None, None
    try:
        store = store or storage()
        data, source_version = store.read_uploaded(asset)
        result = inspect_file(data, declared_mime=asset.declared_mime, expected_bytes=asset.expected_bytes)
        # The snapshotted policy cannot silently downgrade if deployment changes.
        options = scan_options()
        if asset.scanner_policy == "clamav":
            options["backend"] = "clamav"
        scanned = scan(ScanReader(data), **options)
        require(scanned.status in ("clean", "skipped"), "stage_file_infected", status=400)
        result.update(scan_status=scanned.status, scanner_version=scanned.version, staging_version_id=source_version,
                      final_version_id=store.promote_bytes(asset, data, result["sha256"]), error_code="")
    except Exception as exc:
        result = None
        detail = getattr(exc, "detail", {})
        error = getattr(exc, "code", None) or (str(detail.get("code")) if isinstance(detail, dict) and detail.get("code") else "storage_unavailable")
        if error not in {"scanner_unavailable", "scanner_incomplete", "storage_unavailable", "stage_decoder_unavailable",
                         "stage_file_size_mismatch", "stage_file_type_unsupported", "stage_file_invalid", "stage_file_infected", "stage_final_collision"}:
            error = "stage_file_invalid"
    with locked_asset(seed) as current:
        editable(current.assignment, actor=actor)
        finish_validation_locked(current, token=token, result=result, error_code=error)
    return current.state
