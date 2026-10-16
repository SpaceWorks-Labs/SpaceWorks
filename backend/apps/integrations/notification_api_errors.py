from drf_spectacular.utils import OpenApiResponse

from apps.openapi_errors import errors as descriptions


def errors(*codes):
    typed = {"type": "object", "properties": {"detail": {"type": "string"}, "code": {"type": "string"}},
             "required": ["detail"]}
    field_errors = {"type": "object", "additionalProperties": {
        "oneOf": [{"type": "string"}, {"type": "array", "items": {"type": "string"}}, {"type": "object"}],
    }}
    return {code: OpenApiResponse(response={"oneOf": [typed, field_errors]} if code == 400 else typed,
                                 description=description.description)
            for code, description in descriptions(*codes).items()}
