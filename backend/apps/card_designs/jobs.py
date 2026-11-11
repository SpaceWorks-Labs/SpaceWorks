"""Queue, inspect, cancel and download card jobs (#133). The heavy part is `job_runner`.

Scopes: `member_cards` (a space's member cards), `id_programme` (one programme) and
`event` (one event's ID cards). Bulk outputs are capped at 1000 cards per PDF and 300
per ZIP; one bulk job runs per space at a time; a repeated request with the same
inputs returns the same job (idempotency key).
"""
from django.utils.translation import gettext
import hashlib
import json
from datetime import timedelta

from django.db import IntegrityError, transaction
from django.utils import timezone
from rest_framework.exceptions import NotFound, PermissionDenied, ValidationError

from apps.audit import services as audit

from .models import CardJob
from .models_jobs import BULK_KINDS
from .default_templates import REVISION as TEMPLATE_REVISION

RESULT_TTL = timedelta(days=7)
CAPS = {"bulk_sheet": 1000, "bulk_per_person": 1000, "zip": 300, "email": 2000, "wallet_update": 5000}
SCOPE_KINDS = {"member_cards": "member_card", "id_programme": "programme_card", "event": "event_card",
              "staff_cards": "staff_card"}
STAFF_KINDS = ("bulk_sheet", "bulk_per_person", "zip", "email")


def holder_kind(job):
    return SCOPE_KINDS[job.scope]


def _key(kind, scope, scope_id, targets, params, revision):
    if kind in BULK_KINDS:
        revision = {"designs": revision, "templates": TEMPLATE_REVISION}
    raw = json.dumps([kind, scope, scope_id, sorted(targets), params, revision], sort_keys=True, default=str)
    return hashlib.sha256(raw.encode()).hexdigest()


def clean_params(kind, params):
    params = dict(params or {})
    if kind == "bulk_sheet":
        if params.get("paper", "a4") not in ("a4", "letter", "per_card") or params.get("order", "duplex") not in (
                "duplex", "fronts_then_backs"):
            raise ValidationError({"params": gettext("Choose A4, Letter or one card per page, and duplex or fronts then backs.")})
        return {"paper": params.get("paper", "a4"), "order": params.get("order", "duplex"),
                "crop_marks": bool(params.get("crop_marks", True))}
    if kind == "email":
        return {"explicit": bool(params.get("explicit", False))}
    return {}


@transaction.atomic
def enqueue(actor, makerspace, kind, *, scope, scope_id=None, targets, params=None, revision=None):
    if kind not in CardJob.Kind.values or scope not in SCOPE_KINDS:
        raise ValidationError({"kind": gettext("Unknown card job.")})
    targets = sorted({int(value) for value in targets})
    if not targets:
        raise ValidationError({"targets": gettext("No cards match this selection.")})
    cap = CAPS.get(kind)
    if cap and len(targets) > cap:
        raise ValidationError({"targets": gettext('One job holds at most {cap} cards; this selection has {value}. Narrow the filter or split it.').format(cap=cap, value=len(targets))})
    params = clean_params(kind, params)
    key = _key(kind, scope, scope_id, targets, params, revision)
    existing = CardJob.objects.filter(makerspace=makerspace, kind=kind, idempotency_key=key).first()
    if existing is not None and (not existing.finished or existing.state == CardJob.State.SUCCEEDED
                                 and existing.result_expires_at and existing.result_expires_at > timezone.now()):
        return existing, False
    if existing is not None:
        key = _key(kind, scope, scope_id, targets, params, f"{revision}:{timezone.now().isoformat()}")
    if kind in BULK_KINDS and CardJob.objects.filter(makerspace=makerspace, kind__in=BULK_KINDS,
                                                     state__in=("queued", "running")).exists():
        raise ValidationError({"detail": gettext("Another print job is running for this space. Wait for it or cancel it.")})
    try:
        with transaction.atomic():
            job = CardJob.objects.create(makerspace=makerspace, kind=kind, scope=scope, scope_id=scope_id,
                                         requested_by=actor, params=params, targets=targets, total=len(targets),
                                         idempotency_key=key)
    except IntegrityError:
        raise ValidationError({"detail": gettext("Another print job is running for this space.")}) from None
    audit.record(actor, "card_job.queued", makerspace=makerspace, target=job,
                 meta={"job_id": job.pk, "kind": kind, "count": len(targets), "scope": scope})
    from .tasks import dispatch
    transaction.on_commit(lambda: dispatch(job.pk), robust=True)
    return job, True


def visible_to(actor, job):
    """The requester only, plus the platform superadmin (Lane D surface)."""
    from apps.accounts.pii_presentation import is_platform_superadmin
    return bool(actor and (job.requested_by_id == actor.pk or is_platform_superadmin(actor)))


def my_jobs(actor, scope, scope_id, limit=20):
    """The actor's own latest jobs for one programme or event (the list the page polls)."""
    from .serializers import CardJobSerializer
    rows = CardJob.objects.filter(scope=scope, scope_id=scope_id, requested_by=actor).order_by("-created_at")[:limit]
    return CardJobSerializer(rows, many=True).data


def get_any(actor, job_id):
    job = CardJob.objects.select_related("makerspace").filter(pk=job_id).first()
    if job is None or not visible_to(actor, job):
        raise NotFound()
    return job


def get_for(actor, makerspace, job_id):
    job = CardJob.objects.filter(makerspace=makerspace, pk=job_id).first()
    if job is None or not visible_to(actor, job):
        raise NotFound()
    return job


@transaction.atomic
def cancel(actor, job):
    job = CardJob.objects.select_for_update().get(pk=job.pk)
    if job.finished:
        return job
    job.state, job.finished_at = CardJob.State.CANCELLED, timezone.now()
    job.save(update_fields=["state", "finished_at"])
    audit.record(actor, "card_job.cancelled", makerspace=job.makerspace, target=job, meta={"job_id": job.pk})
    from .job_outputs import discard_parts
    transaction.on_commit(lambda: discard_parts(job.pk), robust=True)
    return job


def result_link(actor, job):
    from .storage import signed_url
    if job.state != CardJob.State.SUCCEEDED or not job.result_key:
        raise ValidationError({"detail": gettext("This job has no file to download.")})
    if job.result_expires_at and job.result_expires_at <= timezone.now():
        raise ValidationError({"detail": gettext("This file has expired. Run the job again.")})
    from apps.accounts.pii_presentation import is_platform_superadmin, require_pii_access
    if job.requested_by_id != actor.pk:
        if not is_platform_superadmin(actor):
            raise PermissionDenied()
        require_pii_access(actor, job.makerspace_id)
    audit.record(actor, "card_job.result_downloaded", makerspace=job.makerspace, target=job, meta={"job_id": job.pk})
    extension = {"application/zip": "zip", "application/pdf": "pdf"}.get(job.result_content_type, "bin")
    return signed_url(job.result_key, filename=f"cards-{job.pk}.{extension}")
