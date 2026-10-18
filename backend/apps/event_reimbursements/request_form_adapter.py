"""Fixed mapping over F's validator; never derive money from arbitrary forms."""
from dataclasses import dataclass, field
from decimal import Decimal
from django.utils import timezone
from apps.forms_schema.submission import validate_submission
from apps.payments.event_payouts.errors import require
from .serializers_request import ReimbursementRequestSubmissionSerializer


@dataclass(frozen=True)
class PreparedRequest:
    event_id: int
    owner_member_id: int
    operation_id: object
    programme_id: int
    programme_version: int
    normalized: dict = field(repr=False)
    snapshot: dict = field(repr=False)


def schema(programme):
    questions = [{"id": "estimate_" + category, "type": "money", "label": category.replace("_", " ").title(),
        "required": False, "money": {"currencies": [programme.currency], "min_minor": 1,
        "max_minor": 9_000_000_000_000_000}, "disclosure": {"organizer": True, "reviewer": True, "judge": False}}
        for category in programme.allowed_categories]
    questions += [{"id": "itinerary", "type": "itinerary", "label": "Journey", "required": True,
        "itinerary": {"modes": ["rail", "air", "bus", "car", "other"]}, "sensitive": True,
        "disclosure": {"organizer": False, "reviewer": False, "judge": False}},
        {"id": "need_statement", "type": "long_text", "label": "Support needed", "required": True,
         "bounds": {"max_length": 5000}, "sensitive": True,
         "disclosure": {"organizer": False, "reviewer": False, "judge": False}}]
    return {"schema_version": 2, "form_id": f"reimbursement-request-{programme.pk}",
            "revision": programme.version, "questions": questions}


def context(programme):
    value = schema(programme)
    return {"programme_id": programme.pk, "programme_version": programme.version,
        "form": {key: value[key] for key in ("schema_version", "form_id", "revision")}, "schema": value}


def prepare(*, programme, event, actor, operation_id, block):
    serializer = ReimbursementRequestSubmissionSerializer(data=block)
    serializer.is_valid(raise_exception=True)
    value = serializer.validated_data
    require(programme.event_id == event.pk and programme.enabled, "reimbursement_unavailable")
    require((value["programme_id"], value["programme_version"]) == (programme.pk, programme.version),
            "programme_version_changed")
    require(all(row["category"] in programme.allowed_categories and row["currency"] == programme.currency
                for row in value["estimates"]), "programme_currency_mismatch", status=400)
    distance = value.get("distance_km")
    if programme.min_distance_km is not None:
        require(distance is not None and Decimal(distance) >= programme.min_distance_km,
                "minimum_distance_not_met", status=400)
    answers = {"estimate_" + row["category"]: {"amount_minor": row["amount_minor"], "currency": row["currency"]}
               for row in value["estimates"]}
    answers.update(itinerary=value["itinerary"], need_statement=value["need_statement"])
    validated = validate_submission(schema=schema(programme), payload={"form": value["form"],
        "answers": answers, "derivations": {}, "save_choices": {}, "saved_detail_versions": {}})
    normalized = {row["id"]: row["value"] for row in validated.snapshot["answers"]}
    value = {**value, "itinerary": normalized["itinerary"], "need_statement": normalized["need_statement"]}
    return PreparedRequest(event.pk, actor.pk, operation_id, programme.pk, programme.version, value, validated.snapshot)


def recheck_locked(prepared, *, programme, event, actor, phase):
    require(isinstance(prepared, PreparedRequest) and (prepared.event_id, prepared.owner_member_id,
        prepared.programme_id, prepared.programme_version) == (event.pk, actor.pk, programme.pk, programme.version),
        "programme_version_changed")
    now = timezone.now()
    require(programme.enabled and programme.request_phase in (phase, "both"), "request_phase_closed")
    require((programme.request_opens_at is None or programme.request_opens_at <= now)
        and (programme.request_closes_at is None or now < programme.request_closes_at), "request_window_closed")
