"""Read-only delivery facts; encrypted mappings supplement, never duplicate a leg.

Only original outcome/rank/reason leaves the private history reader. Canonical
callbacks remain authoritative; no sender, contact, body or provider ID is output.
"""
import json
import logging
from itertools import islice

from django.db.models import Q

from apps.integrations.models_contract import NotificationDelivery
from apps.integrations.models_cutover import NotificationLegacyMapping
from apps.makerspaces.secrets import decrypt_value

logger = logging.getLogger(__name__)
PROGRESS = {"accepted": 1, "sent": 2, "delivered": 3, "read": 4}
OUTCOMES = (*PROGRESS, "failed", "skipped", "suppressed", "pending", "sending", "held")
SKIP_REASONS = (
    "tenant_unservable", "module_disabled", "feature_unavailable", "matrix_disabled",
    "account_inactive", "no_membership", "no_tenant_tie", "membership_opted_out",
    "recipient_changed", "personal_disabled", "phone_unverified", "no_consent",
    "sender_unavailable", "no_template", "quota_exceeded", "source_changed",
    "identity_unconfirmed", "live_eligibility_changed", "integration_changed",
    "transport_suppressed", "migration_cancelled", "migration_unknown_outcome",
)
SUPPRESSED = ("transport_suppressed", "suppressed", "provider_opt_out", "21610")


def delivery_facts(queryset):
    fields = (
        "id", "makerspace_id", "channel", "state", "last_error", "attempt_count",
        "claim_until", "provider_source", "estimated_segments", "billed_segments",
        "created_at", "accepted_at", "sent_at", "delivered_at", "read_at", "failed_at",
        "historical", "envelope__feature", "envelope__audience", "envelope__source_kind", "envelope__source_id",
    )
    rows = queryset.order_by("pk").values(*fields).iterator(chunk_size=500)
    while batch := list(islice(rows, 500)):
        # One indexed legacy-PK lookup per batch, rather than a correlated scan of
        # the unindexed canonical_id column for every delivery. M's conversion
        # permanently identifies imported envelope source IDs with the old PK.
        ids = []
        for row in batch:
            source = row["envelope__source_id"]
            if (row["historical"] and row["envelope__source_kind"] == "migration.history"
                    and source.isascii() and source.isdigit() and len(source) <= 19 and int(source) < 2**63):
                ids.append(int(source))
        mappings = NotificationLegacyMapping.objects.filter(
            Q(legacy_model="MessagingDelivery", legacy_id__in=ids) |
            Q(legacy_model="NotificationDelivery.T", legacy_id__in=[row["id"] for row in batch]),
            canonical_model="NotificationDelivery").values("canonical_id", "makerspace_id", "snapshot")
        snapshots = {(m["makerspace_id"], m["canonical_id"]): m["snapshot"] for m in mappings}
        for row in batch:
            original = _original(snapshots.get((row["makerspace_id"], row["id"])))
            yield _fact(row, original)


def _fact(row, original):
    rank = max(PROGRESS.get(row["state"], 0), original.get("rank", 0), *(
        value if row[state + "_at"] else 0 for state, value in PROGRESS.items()))
    state = row["state"]
    if state == "failed" and rank >= 3:
        state = "read" if rank == 4 else "delivered"
    elif state == "retrying":
        state = "sending" if row["claim_until"] else "pending"
    elif state == "skipped" and (row["last_error"] in SUPPRESSED or original.get("status") == "suppressed"):
        state = "suppressed"
    row["status"] = state if state in OUTCOMES else "unknown"
    row["progress"] = rank
    reason = row["last_error"] or original.get("reason", "")
    row["skip_reason"] = (reason if reason in SKIP_REASONS else "unknown") if state in {"skipped", "suppressed"} else "none"
    return row


def _original(snapshot):
    if not snapshot:
        return {}
    try:
        data = json.loads(decrypt_value(snapshot))
        rank = data.get("progress_rank")
        return {"rank": max(rank if type(rank) is int and 0 <= rank <= 4 else 0, PROGRESS.get(data.get("state"), 0)),
                "status": data.get("status"), "reason": data.get("skip_reason")}
    except Exception as exc:  # Unreadable provenance cannot invent progress.
        logger.error("notification_report_history_unreadable", extra={"error_type": type(exc).__name__})
        return {}


def canonical_deliveries():
    return NotificationDelivery.objects.all()
