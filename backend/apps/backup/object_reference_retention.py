"""Typed retention projections, retained even when Events runtime is removed.

Registration names columns only. It never imports a domain model or queries data.
"""

from dataclasses import dataclass
import re
from typing import Callable

from .build_errors import BackupBuildError


@dataclass(frozen=True)
class RetentionProjection:
    retention_state: str = "live"
    object_expired_at: object | None = None
    expired_size_bytes: int | None = None
    capture: bool = True
    expected_size_bytes: int | None = None
    expected_sha256: str | None = None


@dataclass(frozen=True)
class RetentionFieldAdapter:
    query_fields: tuple[str, ...]
    project: Callable


def evidence_projection(row, capture_at):
    state = row.get("object_retention_state__status") or "live"
    expired_at = row.get("object_retention_state__object_expired_at")
    if state in {"expiring", "cleaning"}:
        raise BackupBuildError("Evidence expiry or cleanup is in progress; retry archive capture later.")
    if state not in {"live", "expired"} or (state == "expired" and expired_at is None):
        raise BackupBuildError("Evidence has an invalid retention state.")
    return RetentionProjection(state, expired_at, row.get("object_retention_state__expired_size_bytes"))


def event_asset_projection(row, capture_at):
    state, expired_at = row["state"], row["expired_at"]
    if state in {"expiring", "deleting", "copying", "promoting", "validating"}:
        raise BackupBuildError("Event asset cleanup or promotion is in progress; retry archive capture later.")
    if state == "expired":
        if expired_at is None or type(row["expired_size_bytes"]) is not int or row["expired_size_bytes"] < 0:
            raise BackupBuildError("Expired event asset lacks terminal state.")
        return RetentionProjection("expired", expired_at, row["expired_size_bytes"])
    if expired_at is not None:
        raise BackupBuildError("Event asset has inconsistent terminal retention metadata.")
    if state == "ready":
        if row["expires_at"] is not None and row["expires_at"] <= capture_at:
            raise BackupBuildError("Event asset retention-finalization-required; retry after lifecycle expiry.")
        if not row["actual_bytes"]:
            raise BackupBuildError("Ready event asset lacks canonical size.")
        if not isinstance(row["sha256"], str) or not re.fullmatch(r"[a-f0-9]{64}", row["sha256"]):
            raise BackupBuildError("Ready event asset lacks canonical hash.")
        return RetentionProjection(expected_size_bytes=row["actual_bytes"], expected_sha256=row["sha256"])
    if state in {"reserved", "uploading", "uploaded", "rejected", "quarantined", "aborted"}:
        return RetentionProjection(capture=False)
    raise BackupBuildError("Event asset has an unknown retention state.")


def account_asset_projection(row, capture_at):
    if row["state"] == "ready":
        return RetentionProjection()
    if row["state"] == "deleting":
        raise BackupBuildError("Account asset deletion is in progress; retry archive capture later.")
    if row["state"] in {"uploading", "validating", "failed", "deleted"}:
        return RetentionProjection(capture=False)
    raise BackupBuildError("Account asset has an unknown lifecycle state.")


def private_upload_projection(row, capture_at):
    """Stage-form files and finance attachments share one upload state machine."""
    state = row["state"]
    if state == "deleting":
        raise BackupBuildError("Private upload deletion is in progress; retry archive capture later.")
    if state in {"expired", "deleted"}:
        if row["expired_at"] is None:
            raise BackupBuildError("Expired private upload lacks terminal state.")
        return RetentionProjection("expired", row["expired_at"], int(row["actual_bytes"] or 0))
    if state in {"ready", "attached"}:
        if not row["actual_bytes"]:
            raise BackupBuildError("Ready private upload lacks canonical size.")
        if not isinstance(row["sha256"], str) or not re.fullmatch(r"[a-f0-9]{64}", row["sha256"]):
            raise BackupBuildError("Ready private upload lacks canonical hash.")
        return RetentionProjection(expected_size_bytes=row["actual_bytes"], expected_sha256=row["sha256"])
    if state in {"initiated", "uploaded", "validating", "failed"}:
        return RetentionProjection(capture=False)
    raise BackupBuildError("Private upload has an unknown retention state.")


_PRIVATE_UPLOAD_COLUMNS = ("state", "expired_at", "actual_bytes", "sha256")
ADAPTERS = {
    ("events.StageFormAsset", "object_key"): RetentionFieldAdapter(
        _PRIVATE_UPLOAD_COLUMNS, private_upload_projection),
    ("payments.FinanceAttachment", "object_key"): RetentionFieldAdapter(
        _PRIVATE_UPLOAD_COLUMNS, private_upload_projection),
    ("accounts.MemberSavedAsset", "object_key"): RetentionFieldAdapter(("state",), account_asset_projection),
    ("evidence.EvidencePhoto", "object_key"): RetentionFieldAdapter((
        "object_retention_state__status", "object_retention_state__object_expired_at",
        "object_retention_state__expired_size_bytes",
    ), evidence_projection),
    ("events.SubmissionAsset", "object_key"): RetentionFieldAdapter((
        "state", "expires_at", "expired_at", "expired_size_bytes", "actual_bytes", "sha256",
    ), event_asset_projection),
    ("events.HackathonParticipantAsset", "object_key"): RetentionFieldAdapter((
        "state", "expires_at", "expired_at", "expired_size_bytes", "actual_bytes", "sha256",
    ), event_asset_projection),
}


def adapter_for(rule):
    adapter = ADAPTERS.get((rule.model_label, rule.field_name))
    if rule.retention_aware and adapter is None:
        raise BackupBuildError(f"No retention adapter for {rule.model_label}.{rule.field_name}.")
    return adapter if rule.retention_aware else None
