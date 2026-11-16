"""Deterministic free job admission before claims, freezes or decryption.

These bounds describe supported inputs, not an assertion of a measured runtime.
Full deployments never query or apply this policy.
"""
from pathlib import Path

from django.apps import apps
from django.conf import settings
from django.db import connection

MAX_ROWS = 500
MAX_LOGICAL_BYTES = 2 * 1024 * 1024
MAX_ARCHIVE_FILES = 512
MAX_OBJECTS = 4


class FreeJobTooLarge(ValueError):
    pass


def free():
    return getattr(settings, "SPACEWORKS_DEPLOYMENT_PROFILE", "full") == "free"


def _query_bytes(query):
    sql, params = query.query.sql_with_params()
    with connection.cursor() as cursor:
        # Preserve DISTINCT/joins and bind parameters from Django's compiler.
        # The derived row is expanded on PostgreSQL, never materialised in web RAM.
        cursor.execute("SELECT COALESCE(SUM(octet_length(row_to_json(cloud_bound)::text)), 0) FROM ("
                       + sql + ") cloud_bound", params)
        return cursor.fetchone()[0]


def assert_export(job):
    if not free():
        return
    from apps.data_export.datasets import DATASETS
    from apps.data_export.types import Fidelity
    from apps.data_export.runner import _collect_user_ids
    from apps.data_export.subject_selectors import subject_query
    total_rows, total_bytes, closure = 0, 0, set()
    subject = job.fidelity == "SUBJECT"
    if not subject:
        staff_rows = apps.get_model("makerspaces", "MakerspaceMembership").staff_tracks.filter(
            makerspace_id=job.makerspace_id)
        closure.update(apps.get_model("accounts", "User").objects.filter(
            pk__in=staff_rows.values("user_id")).values_list("pk", flat=True)[:MAX_ROWS + 1])
    fidelity = Fidelity.PORTABLE if subject else Fidelity(job.fidelity)
    for dataset in DATASETS.values():
        if dataset.fidelity is not fidelity or dataset.model == "accounts.User":
            continue
        from .bounded import check
        check()
        model = apps.get_model(dataset.model)
        query = (subject_query(model, job.requested_by, job.makerspace_id) if subject else
                 model.objects.filter(dataset.predicate.as_q(job.makerspace_id)))
        total_rows += query.count()
        if total_rows > MAX_ROWS:
            raise FreeJobTooLarge("This export exceeds the free profile's 500-row limit; use an external full worker.")
        total_bytes += _query_bytes(query)
        if total_bytes > MAX_LOGICAL_BYTES:
            raise FreeJobTooLarge("This export exceeds the free profile's 2 MiB logical-row limit; use an external full worker.")
        if not subject:
            _collect_user_ids(dataset, list(query[:MAX_ROWS + 1]), closure)
    users = apps.get_model("accounts", "User").objects.filter(
        pk=job.requested_by_id) if subject else apps.get_model("accounts", "User").objects.filter(pk__in=closure)
    if total_rows + users.count() > MAX_ROWS or total_bytes + _query_bytes(users) > MAX_LOGICAL_BYTES:
        raise FreeJobTooLarge("This account closure exceeds the free export limit; use an external full worker.")
    if job.fidelity == "PORTABLE":
        # Source closure requires draining every issued presign. A request-sized
        # tick cannot shorten or skip that security window.
        if settings.TENANT_MIGRATION_PRESIGN_DRAIN_SECONDS > 0:
            raise FreeJobTooLarge("Portable source capture requires an external full worker to drain issued uploads.")
        from apps.makerspaces.storage_key_collectors import collect_private_object_keys, collect_public_image_keys
        if collect_private_object_keys(job.makerspace, include_coordination=False) or collect_public_image_keys(job.makerspace, include_coordination=False):
            raise FreeJobTooLarge("Portable capture with object bytes requires an external full worker.")


def assert_report(schedule):
    if free():
        from types import SimpleNamespace
        assert_export(SimpleNamespace(fidelity="REDACTED", makerspace_id=schedule.makerspace_id,
            makerspace=schedule.makerspace, requested_by=schedule.created_by,
            requested_by_id=schedule.created_by_id))


def ciphertext_size(value):
    from apps.backup.managed import staging
    return staging._row(value).size if staging.is_locator(value) else Path(value).stat().st_size


def assert_ciphertext(value):
    if free():
        try:
            size = ciphertext_size(value)
        except (OSError, ValueError):
            raise FreeJobTooLarge("Import size cannot be proven; use an external full worker.") from None
        if not 0 < size <= MAX_LOGICAL_BYTES:
            raise FreeJobTooLarge("This import exceeds the free profile's 2 MiB ciphertext limit; use an external full worker.")


def admit_import(job):
    if not free() or job is None:
        return True
    try:
        assert_ciphertext(job.archive_path)
    except FreeJobTooLarge as exc:
        from django.db import transaction
        from django.utils import timezone
        from apps.audit.services import record
        with transaction.atomic():
            changed = type(job).objects.filter(pk=job.pk, status=job.status,
                target_makerspace__isnull=True).update(status="failed", failure_code="free_job_limit",
                    failure_detail=str(exc), terminal_at=timezone.now(), updated_at=timezone.now())
            if changed:
                record(job.actor, "tenant_migration.import_staging_failed", target=job,
                       meta={"import_id": str(job.pk), "failure_code": "free_job_limit", "format_version": 1})
        return False
    return True


def assert_archive(root):
    if not free():
        return
    import csv
    files = []
    for path in Path(root).rglob("*"):
        if path.is_file():
            files.append(path)
            if len(files) > MAX_ARCHIVE_FILES:
                raise FreeJobTooLarge("This import exceeds the free archive file limit; use an external full worker.")
    if len(files) > MAX_ARCHIVE_FILES or sum(path.stat().st_size for path in files) > MAX_LOGICAL_BYTES:
        raise FreeJobTooLarge("This import exceeds the free archive size/file limit; use an external full worker.")
    rows = 0
    for path in files:
        if path.suffix == ".csv":
            with path.open(encoding="utf-8", newline="") as handle:
                reader = csv.reader(handle)
                next(reader, None)
                for row in reader:
                    rows += 1
                    if rows > MAX_ROWS:
                        raise FreeJobTooLarge("This import exceeds the free profile's 500-row limit; use an external full worker.")
    objects = [path for path in files if "objects" in path.relative_to(root).parts and path.name != "manifest.jsonl"]
    if len(objects) > MAX_OBJECTS:
        raise FreeJobTooLarge("This import exceeds the free profile's four-object limit; use an external full worker.")
