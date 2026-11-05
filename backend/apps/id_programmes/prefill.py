"""Saved-details prefill for a programme's join form (#28, SPEC §5.2 "answers prefilled").

Opt-in and PII-safe by construction:
* the person asks for it (the join page has a "Fill from my Saved details" button); nothing
  is read before that, and nothing is written -- the values only become answers if the
  person submits the form;
* only the signed-in owner's own Saved details are read, for this programme's questions
  that an organiser mapped to a Saved-details key;
* only non-sensitive, single-value keys are allowed (never the date of birth, emergency
  contact, dietary or accessibility needs, the resume or multi-choice skills), and a
  choice question only takes a value that is one of its options;
* the response is `no-store` and is never logged or audited (it is the person's own data).
"""
from apps.forms_schema.profile_fields import PROFILE_FIELDS

# Programme question types are text | choice | email | phone (questions.TYPES).
PREFILL_KEYS = ("name", "phone", "institution", "organization", "study_level", "country", "shirt_size",
                "github_url", "linkedin_url", "portfolio_url")
MAX_VALUE = 500


def allowed(key):
    field = PROFILE_FIELDS.get(key)
    return key in PREFILL_KEYS and field is not None and not field.sensitive and field.persistable


def saved_values(user, keys):
    """The owner's own live Saved details for these keys; {} when the vault cannot be read.

    A locked vault, a missing account key or an account that may not hold Saved details
    simply has nothing to offer: the join form still works by hand.
    """
    from apps.accounts.saved_details.access import require_owner
    from apps.accounts.saved_details.crypto import open_value
    from apps.accounts.saved_details.errors import SavedDetailsError
    from apps.accounts.saved_details.models import MemberSavedDetail
    from apps.encryption.services import PiiUnavailable
    try:
        require_owner(user.pk)
        rows = MemberSavedDetail.objects.filter(user_id=user.pk, field_key__in=set(keys), deleted_at__isnull=True)
        return {row.field_key: open_value(row, "value_envelope") for row in rows}
    except (SavedDetailsError, PiiUnavailable):
        return {}


def values_for(user, programme):
    """-> {question key: value} from the owner's Saved details; {} when nothing applies."""
    questions = [question for question in programme.form_schema or () if allowed(question.get("saved_details_key", ""))]
    if not questions:
        return {}
    saved = saved_values(user, {question["saved_details_key"] for question in questions})
    result = {}
    for question in questions:
        value = saved.get(question["saved_details_key"])
        if not isinstance(value, str) or not value.strip() or len(value) > MAX_VALUE:
            continue
        if question.get("type") == "choice" and value not in (question.get("options") or ()):
            continue
        result[question["key"]] = value.strip()
    return result
