"""Storage guard after F validation/P derivation binding, before C snapshots."""
from django.utils.translation import gettext
import json
from .errors import ProgrammeError


def canonical_answers(value):
    try:
        document = json.loads(value)
        if not isinstance(document, dict) or document.get("version") != 2 or not isinstance(document.get("answers"), list):
            raise ValueError()
        for answer in document["answers"]:
            if not isinstance(answer, dict):
                raise ValueError()
            if answer.get("type") == "age_at_event" and (
                type(answer.get("derivation_id")) is not int or answer["derivation_id"] < 1
                or set(answer) - {"id", "label", "type", "derivation_id"}):
                raise ValueError()
        return json.dumps(document, separators=(",", ":"), ensure_ascii=False, allow_nan=False)
    except (ValueError, TypeError) as exc:
        raise ProgrammeError("invalid_validated_form", gettext("The validated form cannot be stored safely."), status=503) from exc
