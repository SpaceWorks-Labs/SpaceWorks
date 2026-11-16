"""Join-form answers a member card may print (O-B4, parity C18).

A question is printable only when its join form marks it `printable: true` (forms_schema v2, default
false; sensitive and compound types can never be printable). The card prints the answer the member gave
in the application that admitted them: choices by their label, multi-select joined with ", ", capped at
200 characters. The design places it as `{{field:<key>}}`, `<key>` being the question id lower-cased with
`-` as `_`. Anything that cannot be read prints nothing.
"""
import re

MAX_CHARS = 200
_KEY = re.compile(r"[^a-z0-9_]")


def tag_key(question_id):
    return _KEY.sub("_", str(question_id).lower().replace("-", "_"))[:40]


def _choice_text(question, value):
    labels = {option.get("id"): option.get("label") for option in question.get("options", ())
              if isinstance(option, dict)}
    ids = value.get("option_ids", [value.get("option_id")] if value.get("option_id") else [])
    parts = [str(labels.get(i) or i) for i in ids]
    if value.get("other"):
        parts.append(str(value["other"]))
    return ", ".join(parts)


def _text(question, value):
    if isinstance(value, dict):
        return _choice_text(question, value)
    if isinstance(value, bool):
        return "Yes" if value else "No"
    if isinstance(value, (list, tuple)):
        return ", ".join(str(item) for item in value)
    return "" if value is None else str(value)


def printable_values(membership):
    """-> {"field:<key>": text} for the member's printable join answers; {} when there are none."""
    from apps.makerspaces.membership_admission_forms import answers_for
    from apps.makerspaces.models import MembershipRequest
    if membership is None:
        return {}
    row = (MembershipRequest.objects.filter(makerspace_id=membership.makerspace_id, user_id=membership.user_id,
                                            state="active").exclude(application_schema__isnull=True)
           .order_by("-decided_at", "-pk").first())
    schema = row.application_schema if row else None
    if not isinstance(schema, dict):
        return {}
    printable = {q["id"]: q for q in schema.get("questions", ())
                 if isinstance(q, dict) and q.get("printable") is True and not q.get("sensitive")}
    snapshot = answers_for(row) if printable else None
    values = {}
    for answer in (snapshot or {}).get("answers", ()):
        question = printable.get(answer.get("id"))
        if question is None or answer.get("sensitive"):
            continue
        text = _text(question, answer.get("value")).strip()
        if text:
            values[f"field:{tag_key(answer['id'])}"] = text[:MAX_CHARS]
    return values
