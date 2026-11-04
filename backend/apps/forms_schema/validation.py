"""Version dispatch; legacy callers retain their snapshots and errors."""
from .legacy import ALLOWED_QUESTION_TYPES


def validate_form_schema(value, *, context=None):
    if isinstance(value, dict):
        from .schema_v2 import validate_schema
        return validate_schema(value, context=context)
    from .legacy import validate_form_schema as legacy
    return legacy(value)


def validate_answers(schema, raw_answers, *, context=None, file_resolver=None):
    if isinstance(schema, dict):
        from .submission import validate_submission
        from .profile_fields import PROFILE_FIELDS
        return validate_submission(schema=schema, context=context, file_resolver=file_resolver, payload={"answers": raw_answers,
            "save_choices": {key: False for key, field in PROFILE_FIELDS.items() if field.persistable}}).snapshot
    from .legacy import validate_answers as legacy
    return legacy(schema, raw_answers)
