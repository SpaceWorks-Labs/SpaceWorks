"""Normalize reusable compound values through F, then pin canonical domain lines."""
from apps.forms_schema.submission import validate_submission
from apps.payments.event_payouts.errors import require


def validate_line_form(line, *, claim):
    questions = [
        {"id": "amount", "type": "money", "label": "Receipt amount", "required": True,
            "money": {"currencies": [line["original_currency"]], "min_minor": 1, "max_minor": 9000000000000000}},
        {"id": "receipt", "type": "file", "label": "Receipt", "required": True, "sensitive": True,
            "file": {"purpose": "reimbursement_receipt", "max_files": 1, "max_bytes_each": 10485760}},
    ]
    ref = line["receipt"]
    payload = {"form": {"schema_version": 2, "form_id": f"claim-line-{line['line_uuid']}", "revision": 1},
        "answers": {"amount": {"amount_minor": line["original_amount_minor"], "currency": line["original_currency"]},
            "receipt": [{key: ref[key] for key in ("asset_id", "generation", "sha256")}]},
        "derivations": {}, "save_choices": {}, "saved_detail_versions": {}}
    if line["category"] != "lodging":
        questions.append({"id": "route", "type": "itinerary", "label": "Journey", "required": True,
            "sensitive": True, "itinerary": {"modes": ["rail", "air", "bus", "car", "other"]}})
        payload["answers"]["route"] = line["route"]
    schema = {**payload["form"], "questions": questions}
    def resolve(*, question, reference):
        from .receipt_uploads import owned_asset
        asset = owned_asset(event=claim.event, owner_id=claim.member_id, asset_id=reference["asset_id"])
        require(question["file"]["purpose"] == "reimbursement_receipt" and asset.binding_uuid == claim.uuid
            and asset.generation == reference["generation"] and asset.sha256 == reference["sha256"]
            and asset.state in ("ready", "attached") and asset.scan_status in ("clean", "skipped")
            and asset.actual_bytes == asset.expected_bytes and asset.actual_bytes <= question["file"]["max_bytes_each"]
            and asset.canonical_mime in ("application/pdf", "image/jpeg", "image/png", "image/heic", "image/heif"),
            "receipt_unavailable", status=404)
        return True
    return validate_submission(schema=schema, payload=payload, context="claim", file_resolver=resolve)
