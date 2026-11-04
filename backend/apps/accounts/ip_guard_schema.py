"""OpenAPI: the login IP guard's, Turnstile's and the breach check's errors on every route
they can answer (a drf-spectacular postprocessing hook, so ~20 sign-in views owned by
other lanes need no edit and a newly flagged view is documented automatically).

- every guarded operation: 429 ``ip_blocked`` (``Retry-After`` when the block ends);
- CAPTCHA routes: 400 ``captcha_required`` / ``captcha_failed``;
- routes that set a password: 400 with ``code: password_breached``.
"""

from django.urls import NoReverseMatch, reverse

ERROR_SCHEMA = "LoginGuardError"
_SCHEMA = {
    "type": "object",
    "properties": {
        "detail": {"type": "string"},
        "code": {"type": "string", "enum": ["ip_blocked", "captcha_required", "captcha_failed"]},
        "turnstile_site_key": {"type": "string", "description": "Captcha refusals only: the widget's site key."},
        "turnstile_action": {"type": "string", "description": "Captcha refusals only: the widget action to use."},
    },
    "required": ["detail", "code"],
}
IP_TEXT = ("`ip_blocked`: a platform deny rule or an automatic block (many accounts failing from one "
           "address) covers this client; `Retry-After` gives the seconds left when the block ends.")
CAPTCHA_TEXT = ("`captcha_required` / `captcha_failed`: Cloudflare Turnstile is on for this origin and "
                "needs a token in the `X-Turnstile-Token` header (after failed sign-ins, a space's "
                "`always` setting, or instead of an automatic block).")
BREACH_TEXT = "`code: password_breached`: the new password appears in a known data breach."
PASSWORD_ROUTES = ("auth-member-sign-up", "auth-change-password", "auth-reset-password",
                   "auth-staff-invitation-accept")


def _path(name):
    try:
        return reverse(name)
    except NoReverseMatch:
        return None


def _document(operation, status, text, with_schema):
    responses = operation.setdefault("responses", {})
    response = responses.setdefault(str(status), {"description": ""})
    if text not in response.get("description", ""):
        response["description"] = f"{response.get('description', '')} {text}".strip()
    if with_schema and "content" not in response:
        response["content"] = {"application/json": {"schema": {"$ref": f"#/components/schemas/{ERROR_SCHEMA}"}}}


def document_login_guard_errors(result, generator, request, public):
    from apps.accounts.ip_guard_middleware import GUARDED_ROUTES, guarded
    from apps.accounts.turnstile import CAPTCHA_ROUTES

    paths = result.get("paths", {})
    targets = {path for path, _regex, _method, callback in getattr(generator, "endpoints", None) or ()
               if guarded(callback, None)}
    targets |= {_path(name) for name in GUARDED_ROUTES}
    captcha = {_path(name) for name in CAPTCHA_ROUTES}
    for path in targets - {None}:
        for method, operation in paths.get(path, {}).items():
            if method in ("get", "post", "put", "patch", "delete") and isinstance(operation, dict):
                _document(operation, 429, IP_TEXT, True)
                if path in captcha and method != "get":
                    _document(operation, 400, CAPTCHA_TEXT, True)
    for path in {_path(name) for name in PASSWORD_ROUTES} - {None}:
        for method, operation in paths.get(path, {}).items():
            if method in ("post", "put", "patch") and isinstance(operation, dict):
                _document(operation, 400, BREACH_TEXT, False)
    result.setdefault("components", {}).setdefault("schemas", {})[ERROR_SCHEMA] = _SCHEMA
    return result
