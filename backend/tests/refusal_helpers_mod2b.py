"""MOD-2B: one exact refusal assertion (status AND error code) for the route-condition tests.

Typed refusals (`module_disabled`, `feature_disabled`, workflow errors) carry `code` in the body. Plain DRF
refusals (`not_authenticated`, `permission_denied`, `not_found`) keep it on the `ErrorDetail` of `detail`, so
the helper reads whichever the response has and compares it with the single decided code.
"""


def error_code(response):
    if "json" not in response.get("Content-Type", ""):
        return None
    body = response.data if hasattr(response, "data") else response.json()
    if isinstance(body, dict) and body.get("code"):
        return body["code"]
    detail = body.get("detail") if isinstance(body, dict) else None
    return getattr(detail, "code", None)


def refused(response, status, code):
    assert response.status_code == status and error_code(response) == code, (
        f"expected {status} {code}, got {response.status_code} {error_code(response)}: {response.content[:300]!r}")
    return response


def module_off(response):
    return refused(response, 404, "module_disabled")


def feature_off(response):
    return refused(response, 404, "feature_disabled")
