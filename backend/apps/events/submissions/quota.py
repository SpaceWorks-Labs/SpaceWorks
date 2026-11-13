"""Event pool accounting, deliberately independent of the ordinary 1 GiB pool."""
from django.db.models import Sum

from .errors import SubmissionError
from .models_assets import EventAssetUsage

MIB = 1024 ** 2
MANAGED_ALLOWANCE = 25_000_000_000
SUBMISSION_CAP = 1536 * MIB
MAX_ASSETS = 100
GROUP_CAPS = {"video": 500, "deck": 50, "images": 50, "source": 200, "hardware-pcb": 150,
              "hardware-cad": 500, "firmware": 50, "fab-2d": 150, "fab-3dprint": 500,
              "fab-cnc": 300, "embroidery": 50, "archives": 200, "resume": 1536}


def usage_locked(context):
    # The boundary already locks the owning event, serializing first-use insertion.
    row, _ = EventAssetUsage.objects.get_or_create(event=context.event, defaults={
        "budget_bytes": (min(MANAGED_ALLOWANCE, context.budget_bytes) if context.budget_bytes is not None
                         else MANAGED_ALLOWANCE) if context.managed else context.budget_bytes,
    })
    return EventAssetUsage.objects.select_for_update().get(pk=row.pk)


def reserve(usage, rows, *, size, group, group_cap_bytes=None):
    live = rows.filter(deleted_at__isnull=True)
    count = live.count()
    sums = live.aggregate(reserved=Sum("reserved_bytes"), charged=Sum("charged_bytes"))
    total = (sums["reserved"] or 0) + (sums["charged"] or 0)
    group_sums = live.filter(kind=group).aggregate(reserved=Sum("reserved_bytes"), charged=Sum("charged_bytes"))
    group_total = (group_sums["reserved"] or 0) + (group_sums["charged"] or 0)
    if count >= MAX_ASSETS or (group == "images" and live.filter(kind="images").count() >= 10):
        raise SubmissionError("asset_count_limit", 413)
    group_cap = GROUP_CAPS[group] * MIB
    if group_cap_bytes is not None:
        if type(group_cap_bytes) is not int or group_cap_bytes < 1:
            raise SubmissionError("invalid_cap")
        group_cap = min(group_cap, group_cap_bytes)
    if total + size > SUBMISSION_CAP or group_total + size > group_cap:
        raise SubmissionError("submission_budget_exceeded", 413)
    if usage.budget_bytes is not None and usage.used_bytes + usage.reserved_bytes + size > usage.budget_bytes:
        raise SubmissionError("storage_budget_exceeded", 413)
    usage.reserved_bytes += size
    usage.save(update_fields=["reserved_bytes"])


def charge(usage, asset, actual_bytes):
    if asset.charged_bytes:
        if asset.charged_bytes != actual_bytes:
            raise SubmissionError("asset_charge_conflict", 409)
        return
    if not 0 < actual_bytes <= asset.reserved_bytes:
        raise SubmissionError("asset_size_conflict", 409)
    # Retain any canonicalization difference until staging/verification deletion.
    usage.reserved_bytes -= actual_bytes
    usage.used_bytes += actual_bytes
    asset.reserved_bytes -= actual_bytes
    asset.charged_bytes = actual_bytes
    usage.save(update_fields=["reserved_bytes", "used_bytes"])


def release_after_cleanup(usage, asset, *, final_deleted):
    usage.reserved_bytes -= asset.reserved_bytes
    asset.reserved_bytes = 0
    if final_deleted:
        usage.used_bytes -= asset.charged_bytes
        asset.charged_bytes = 0
    if min(usage.reserved_bytes, usage.used_bytes) < 0:
        raise SubmissionError("asset_accounting_conflict", 409)
    usage.save(update_fields=["reserved_bytes", "used_bytes"])


def change_budget_locked(usage, budget_bytes, *, event, actor):
    if budget_bytes is not None and (type(budget_bytes) is not int or budget_bytes < usage.used_bytes + usage.reserved_bytes):
        raise SubmissionError("budget_below_usage", 409)
    usage.budget_bytes = budget_bytes
    usage.save(update_fields=["budget_bytes"])
    from apps.audit.services import record
    record(actor, "event.asset_budget_changed", makerspace=event.makerspace, target=usage,
           meta={"budget_bytes": budget_bytes})


def reserve_canonical_difference(usage, asset, actual_bytes, *, group_cap_bytes=None):
    extra = actual_bytes - asset.reserved_bytes
    if extra <= 0:
        return
    if actual_bytes > asset.effective_cap:
        raise SubmissionError("file_too_large", 413)
    rows = type(asset).objects.filter(event_id=asset.event_id, deleted_at__isnull=True)
    rows = rows.filter(member_id=asset.member_id) if hasattr(asset, "member_id") else rows.filter(team_id=asset.team_id)
    sums = rows.aggregate(r=Sum("reserved_bytes"), c=Sum("charged_bytes"))
    grouped = rows.filter(kind=asset.kind).aggregate(r=Sum("reserved_bytes"), c=Sum("charged_bytes"))
    group_cap = min(GROUP_CAPS[asset.kind] * MIB, group_cap_bytes or GROUP_CAPS[asset.kind] * MIB)
    if ((sums["r"] or 0) + (sums["c"] or 0) + extra > SUBMISSION_CAP or
            (grouped["r"] or 0) + (grouped["c"] or 0) + extra > group_cap or
            usage.budget_bytes is not None and usage.used_bytes + usage.reserved_bytes + extra > usage.budget_bytes):
        raise SubmissionError("storage_budget_exceeded", 413)
    asset.reserved_bytes += extra
    usage.reserved_bytes += extra
    usage.save(update_fields=["reserved_bytes"])


def storage_summary(usage):
    from .models_assets import SubmissionAsset, HackathonParticipantAsset
    failed = 0
    for cls in (SubmissionAsset, HackathonParticipantAsset):
        totals = cls.objects.filter(event_id=usage.event_id, deleted_at__isnull=True,
            failure_code="storage_cleanup_pending").aggregate(r=Sum("reserved_bytes"), c=Sum("charged_bytes"))
        failed += (totals["r"] or 0) + (totals["c"] or 0)
    return {"used_bytes": usage.used_bytes, "reserved_bytes": usage.reserved_bytes,
            "available_bytes": None if usage.budget_bytes is None else max(0, usage.budget_bytes - usage.used_bytes - usage.reserved_bytes),
            "failed_cleanup_bytes": failed}
