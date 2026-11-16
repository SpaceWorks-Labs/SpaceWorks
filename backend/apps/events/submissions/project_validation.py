from .errors import SubmissionError

TEXT_BOUNDS = {"title": 200, "tagline": 300, "problem": 10000, "description": 30000, "challenges": 10000}
PROJECT_FIELDS = {*TEXT_BOUNDS, "tech_tags", "ai_declaration", "reuse_declaration", "form_answers",
                  "track_ids", "prize_ids", "asset_ids", "public_asset_ids", "public_requested"}


def validate_project_patch(data):
    if not isinstance(data, dict) or set(data) - PROJECT_FIELDS:
        raise SubmissionError("unknown_project_field")
    for key, value in data.items():
        if key in TEXT_BOUNDS and (not isinstance(value, str) or len(value) > TEXT_BOUNDS[key]):
            raise SubmissionError("invalid_project_text")
        if key == "public_requested" and type(value) is not bool:
            raise SubmissionError("invalid_consent")
        if key == "tech_tags" and (not isinstance(value, list) or len(value) > 30 or
                any(not isinstance(v, str) or not v.strip() or len(v) > 50 for v in value)):
            raise SubmissionError("invalid_tech_tags")
        if key in {"track_ids", "prize_ids", "asset_ids", "public_asset_ids"} and (not isinstance(value, list) or len(value) > 100 or
                any(type(v) is not int or v <= 0 for v in value) or len(set(value)) != len(value)):
            raise SubmissionError("invalid_selection")
        if key in {"ai_declaration", "reuse_declaration"}:
            if (not isinstance(value, dict) or set(value) != {"used", "details"} or
                    type(value["used"]) is not bool or not isinstance(value["details"], str) or
                    len(value["details"]) > 5000 or value["used"] and not value["details"].strip()):
                raise SubmissionError("declaration_required")
        if key == "form_answers" and not isinstance(value, dict):
            raise SubmissionError("invalid_answers")
    return data
