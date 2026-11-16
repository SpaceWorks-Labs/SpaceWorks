"""Owner prefill uses a server-resolved form context, never a client schema."""
from django.utils.translation import gettext
from dataclasses import dataclass
from datetime import date
from typing import Protocol

from apps.encryption.account_readiness import assert_ready

from .access import require_owner
from .age import age_on
from .crypto import open_value
from .errors import SavedDetailsError
from .fields import descriptor
from .models import MemberSavedDetail
from .subject_binding import require_subject


@dataclass(frozen=True, kw_only=True)
class PrefillContext:
    owner_id: int
    event_id: int
    subject_kind: str
    form_id: str
    form_revision: int
    event_date_revision: int
    as_of_date: date
    questions: tuple[dict, ...]  # F visibility-filtered, mapping-compatible questions only
    locked: bool = False
    subject: object | None = None  # G's separate StageResponseSubject for stage contexts
    stage_form_id: int | None = None


class ContextProvider(Protocol):
    def resolve(self, *, actor_id: int, selector: dict) -> PrefillContext:
        """Live eligibility, host/source/module and typed owner resolution, even first use."""
        ...


_provider = None


def install_context_provider(provider: ContextProvider):
    global _provider
    if _provider is not None and _provider is not provider:
        raise RuntimeError("Saved details context provider already installed.")
    _provider = provider


def prefill(actor_id, request):
    require_owner(actor_id)
    assert_ready()
    if _provider is None:
        raise SavedDetailsError("not_found", gettext("Registration context not found."), 404)
    context = _provider.resolve(actor_id=actor_id, selector=request["context"])
    if (context.owner_id != actor_id or context.subject_kind not in {"registration", "application", "role_assignment", "stage_response"}
            or context.event_id != request["context"]["event_id"] or context.subject_kind != request["context"]["subject_kind"]):
        raise SavedDetailsError("not_found", gettext("Registration context not found."), 404)
    if context.subject_kind == "stage_response":
        require_subject(context.subject)
        selector = request["context"]
        subject = context.subject
        if ((subject.event_id, subject.owner_member_id, str(subject.kind)) != (context.event_id, actor_id, "stage_response")
                or subject.subject_id != selector.get("subject_id")
                or subject.creation_operation_id != selector.get("creation_operation_id")
                or "stage_form_id" in selector and context.stage_form_id != selector["stage_form_id"]):
            raise SavedDetailsError("not_found", gettext("Stage form context not found."), 404)
    if (request["form_id"], request["form_revision"]) != (context.form_id, context.form_revision):
        raise SavedDetailsError("form_revision_changed", gettext("Review the revised form."), 409)
    if request["event_date_revision"] != context.event_date_revision:
        raise SavedDetailsError("event_date_changed", gettext("Reload the form for the revised event date."), 409,
                                event_date_revision=context.event_date_revision, as_of_date=context.as_of_date.isoformat())
    stage = context.subject_kind == "stage_response"
    rows = MemberSavedDetail.objects.filter(user_id=actor_id)
    if stage:
        # Do not even load the private source in a context that cannot use it.
        rows = rows.exclude(field_key="date_of_birth")
    rows = {r.field_key: r for r in rows}
    values, versions, defaults, derivations = {}, {}, {}, {}
    for question in context.questions:
        key = question.get("profile_field_key")
        if stage and (key in {"date_of_birth", "age_at_event"} or question.get("type") in {"date_of_birth", "age_at_event"}):
            continue
        if not key:
            continue
        key = "date_of_birth" if key == "age_at_event" else key
        info = descriptor(key)
        defaults[key] = defaults.get(key, True) and info["default_save"] and not question.get("sensitive", False)
        row = rows.get(key)
        if row is not None:
            versions[key] = row.version
        if row is None or row.deleted_at:
            continue
        value = open_value(row, "value_envelope")
        if question["type"] == "age_at_event":
            derivations[question["id"]] = {
                "source": {"kind": "saved_detail", "field_key": "date_of_birth", "version": row.version},
                "value": age_on(date.fromisoformat(value), context.as_of_date), "as_of_date": context.as_of_date.isoformat(),
            }
        elif question["type"] == "single_choice":
            if value in {option["id"] for option in question.get("options", [])}:
                values[key] = value
        elif question["type"] == "multi_choice":
            options = {option["id"] for option in question.get("options", [])}
            if isinstance(value, list) and all(item in options for item in value):
                values[key] = value
        else:
            values[key] = value
    return {"form_revision": context.form_revision, "event_date_revision": context.event_date_revision,
            "values": values, "saved_detail_versions": versions, "save_defaults": defaults, "derivation_inputs": derivations}
