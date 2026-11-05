"""F canonical track answers and D selection eligibility share B's transaction."""
from copy import deepcopy
from apps.events.programme_locks import current_locks
from apps.forms_schema.submission import validate_submission
from .errors import SubmissionError


def validate_project(*, context, project, final):
    from apps.events.judging.eligibility import require_selections_locked
    from apps.events.judging.models_definitions import HackathonTrack, HackathonPrize
    locks = current_locks(context.event.pk)
    if final:
        selected = require_selections_locked(event_id=context.event.pk, team_id=context.team_id,
            track_ids=project["track_ids"], prize_ids=project["prize_ids"],
            tech_tags=project["tech_tags"], locks=locks)
    else:
        selected = {}
        for key, model in (("tracks", HackathonTrack), ("prizes", HackathonPrize)):
            ids = project["track_ids" if key == "tracks" else "prize_ids"]
            rows = list(model.objects.filter(event=context.event, pk__in=ids).order_by("pk"))
            if len(rows) != len(ids):
                raise SubmissionError("not_found", 404)
            selected[key] = [{"id": row.pk, "form": row.form} for row in rows]
    supplied = project["form_answers"]
    canonical = {}
    for group in ("tracks", "prizes"):
        for item in selected[group]:
            key = f"{group[:-1]}:{item['id']}"
            schema = deepcopy(item["form"])
            if not schema:
                continue
            if not final:
                questions = schema if isinstance(schema, list) else schema.get("questions", [])
                for question in questions:
                    question["required"] = False
            # Project forms cannot create an account-owned age source or vault intent.
            questions = schema if isinstance(schema, list) else schema.get("questions", [])
            if any(q.get("type") == "age_at_event" for q in questions):
                raise SubmissionError("project_derivation_unavailable", 503)
            answers = supplied.get(key, {})
            if isinstance(answers, dict) and isinstance(answers.get("answers"), list):
                answers = {row["id"]: row["value"] for row in answers["answers"]
                    if isinstance(row, dict) and "id" in row and "value" in row}
            if not isinstance(answers, dict):
                raise SubmissionError("invalid_answers")
            canonical[key] = validate_submission(schema=schema, payload={"answers": answers}).snapshot
    for key in set(supplied) - set(canonical):
        if key.startswith("stage:"):  # #178 custom stage fields; required ones are enforced at submit.
            answers = _stage_answers(context, key, supplied[key])
            if answers:
                canonical[key] = answers
            continue
        try:
            group, pk = key.split(":")
            model = {"track": HackathonTrack, "prize": HackathonPrize}[group]
            valid = str(int(pk)) == pk and model.objects.filter(event=context.event, pk=int(pk)).exists()
        except (ValueError, KeyError, AttributeError):
            valid = False
        if not valid:
            raise SubmissionError("unknown_project_form")
    return {**project, "form_answers": canonical}


def _stage_answers(context, key, answers):
    """Answers to a stage's custom fields. A deleted stage or field drops its stale answers, never the draft."""
    from .models_stages import SubmissionStage
    from .stage_rules import field_answer
    pk = key.split(":", 1)[1]
    if not isinstance(answers, dict) or not pk.isdigit() or str(int(pk)) != pk:
        raise SubmissionError("invalid_answers")
    stage = SubmissionStage.objects.filter(event=context.event, pk=int(pk)).first()
    fields = {field["key"]: field for field in stage.custom_fields} if stage else {}
    return {name: value for name, value in ((name, field_answer(fields[name], raw))
            for name, raw in answers.items() if name in fields) if value is not None}
