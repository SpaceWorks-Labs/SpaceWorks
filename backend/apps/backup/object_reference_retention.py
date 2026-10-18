"""Typed retention projections, retained even when Events runtime is removed.

Registration names columns only. It never imports a domain model or queries data.
"""

from dataclasses import dataclass
import re
from typing import Callable

from .recipient_selection import BackupBuildError


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


ADAPTERS = {
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
