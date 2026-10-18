from drf_spectacular.utils import OpenApiResponse

from apps.openapi_errors import errors as descriptions


def errors(*codes, **overrides):
    typed = {"type": "object", "properties": {"detail": {"type": "string"}, "code": {"type": "string"}},
             "required": ["detail"]}
    field_errors = {"type": "object", "additionalProperties": {
        "oneOf": [{"type": "string"}, {"type": "array", "items": {"type": "string"}}, {"type": "object"}],
    }}
    return {code: OpenApiResponse(response={"oneOf": [typed, field_errors]} if code == 400 else typed,
                                 description=description.description)
            for code, description in descriptions(*codes, **overrides).items()}


# Credential writes step up exactly like payment credential writes.
REAUTH_403 = ("Signed in, but this action or makerspace is not permitted, or recent_reauth_required: "
              "writing or clearing provider credentials needs identity verification within ten minutes.")
