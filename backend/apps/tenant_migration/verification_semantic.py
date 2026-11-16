"""Pre-commit verification of portable non-FK domain references."""
import json
from django.apps import apps
from apps.accounts.models import User
from .insertion_errors import ImportVerificationError
from .references import (AUDIT_TARGET_DISPOSITIONS, SOURCE_LOCAL_SNAPSHOT_FIELDS,
                         DISCRIMINATOR_REFERENCES, PAYMENT_SUBJECT_REFERENCES, normalize_audit_target_type)
from .audit_references import AuditReferenceDisposition
from .semantic_remap import _remap_notification_url


def _semantic_field_names(label):
    names = []
    if any(edge[0] == label for edge in DISCRIMINATOR_REFERENCES):
        names.extend(("target_type", "target_id"))
    if label == "payments.Payment":
        names.extend(("subject_type", "subject_id"))
    elif label == "machines.ConsumableCostRecord":
        names.extend(("source_kind", "source_id"))
    elif label == "machines.ServiceRequestFile":
        names.append("owner_user_id")
    elif label == "audit.AuditLog":
        names.extend(("target_type", "target_id"))
    elif label == "notifications.Notification":
        names.append("url_path")
    elif label == "hardware_requests.PublicToolLoan":
        names.extend(("asset_ids", "qr_ids"))
    names.extend(name for model, name in sorted(SOURCE_LOCAL_SNAPSHOT_FIELDS) if model == label)
    return list(dict.fromkeys(names))


def _verify_semantic_row(label, source, actual, pk_map, references):
    for model_label, name in SOURCE_LOCAL_SNAPSHOT_FIELDS:
        # Source-local history must arrive byte-for-byte, never rebound to a target id.
        if model_label == label and _snapshot_text(actual[name]) != _snapshot_text(source[name]):
            raise ImportVerificationError(f"A source-local snapshot changed for {label}.{name}.")
    edge = (label, "target_type", "target_id")
    if edge in DISCRIMINATOR_REFERENCES:
        external = references.get(label, source["id"], "target_type+target_id")
        if external:
            if not str(actual["target_type"]).startswith("external_") or actual[
                "target_id"
            ] != 0:
                raise ImportVerificationError(
                    f"External discriminator reference is live for {label}."
                )
        else:
            target_label = DISCRIMINATOR_REFERENCES[edge][source["target_type"]]
            expected = pk_map.lookup(apps.get_model(target_label), source["target_id"])
            if str(actual["target_id"]) != str(expected):
                raise ImportVerificationError(
                    f"Discriminator reference is invalid for {label}."
                )
    if label == "machines.ConsumableCostRecord":
        from .tracking_references import COST_SOURCE_MODELS
        target = apps.get_model(COST_SOURCE_MODELS[source["source_kind"]])
        if actual["source_id"] != pk_map.lookup(target, source["source_id"]):
            raise ImportVerificationError("A consumable cost source reference is invalid.")
    if label == "payments.Payment":
        target_label = PAYMENT_SUBJECT_REFERENCES[source["subject_type"]]
        expected = pk_map.lookup(apps.get_model(target_label), source["subject_id"])
        if actual["subject_id"] != expected:
            raise ImportVerificationError("A payment subject reference is invalid.")
    elif label == "machines.ServiceRequestFile" and source["owner_user_id"]:
        expected = pk_map.lookup(User, source["owner_user_id"])
        if actual["owner_user_id"] != expected:
            raise ImportVerificationError("A raw user reference is unresolved.")
    elif label == "audit.AuditLog" and source["target_id"]:
        disposition = AUDIT_TARGET_DISPOSITIONS.get(
            normalize_audit_target_type(source["target_type"])
        )
        if disposition and disposition.disposition is AuditReferenceDisposition.REMAP:
            expected = pk_map.lookup(
                apps.get_model(disposition.target_model_label), source["target_id"]
            )
            if str(actual["target_id"]) != str(expected):
                raise ImportVerificationError("An audit target reference is invalid.")
    elif label == "notifications.Notification":
        expected = _remap_notification_url(source["url_path"], pk_map)
        if actual["url_path"] != expected:
            raise ImportVerificationError("A notification URL reference is invalid.")
    if label == "hardware_requests.PublicToolLoan":
        _verify_loan_reference_list(
            source, actual, pk_map, references, "asset_ids", "inventory.InventoryAsset"
        )
        _verify_loan_reference_list(
            source, actual, pk_map, references, "qr_ids", "boxes.QrCode"
        )


def _verify_loan_reference_list(source, actual, pk_map, references, field_name, label):
    snapshot = references.external_snapshot(
        "hardware_requests.PublicToolLoan", source["id"], field_name
    )
    missing = {
        int(item["source_id"])
        for item in (snapshot or {}).get("references", [])
    }
    expected = [
        pk_map.lookup(apps.get_model(label), value)
        for value in json.loads(source[field_name] or "[]")
        if int(value) not in missing
    ]
    if actual[field_name] != expected:
        raise ImportVerificationError(f"Loan {field_name} contains an unresolved id.")


def _snapshot_text(value):
    return "" if value is None else str(value)
