"""Literal, content-free operation examples for runtime OpenAPI and G's handoff."""

AT = "2026-12-01T04:00:00Z"
FORM = {"schema_version": 2, "form_id": "registration", "revision": 3, "questions": [
    {"id": "institution", "type": "short_text", "label": "School or organisation", "required": True,
     "profile_field_key": "institution", "bounds": {"max_length": 200},
     "disclosure": {"organizer": True, "reviewer": False, "judge": False}}]}
READINESS = {"event_id": 42, "generated_at": AT, "items": [
    {"code": "cover", "status": "missing", "label": "Add a cover photo",
     "href": "/admin/events?event=42&tab=cover", "count": None}]}
LIVE = {"event_id": 42, "generated_at": AT, "available_from": "2026-12-01T02:00:00Z",
        "doors_open_at": AT, "seconds_until_doors": 0, "active": True, "going": 24, "checked_in": 3,
        "arrivals": [{"starts_at": AT, "count": 3}], "first_run": False}
PUBLISHING = {"event_id": 42, "version": 4, "is_public": False, "listing": "listed", "page_state": "live",
              "registration_audience": "accounts",
              "status": "draft", "website_released": False, "website_revision": 3}
FORM_READ = {"event_id": 42, "version": 4, "form_key": "registration", "schema": FORM}
FORM_PUT = {"operation_id": "11111111-1111-4111-8111-111111111111", "expected_version": 4, "schema": FORM}
FORM_VALIDATION_INPUT = {"schema": FORM, "sample_answers": {"institution": "Maker College"}}
FORM_VALIDATION_RESULT = {"valid": True, "visible_question_ids": ["institution"], "errors": {}}

for _data in (READINESS, LIVE, PUBLISHING):
    _data.update(id=42, version=4, allowed_actions=["edit_details"], state=_data.get("status", "published"))
