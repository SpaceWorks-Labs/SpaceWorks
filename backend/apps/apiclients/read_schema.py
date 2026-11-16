"""OpenAPI conventions for domain-neutral signed read adapters."""

from drf_spectacular.utils import OpenApiParameter, OpenApiResponse

from apps.hardware_requests.exceptions import ErrorSerializer

HMAC_PARAMETERS = [
    OpenApiParameter("X-Client-Id", str, location="header", required=True),
    OpenApiParameter("X-Timestamp", str, location="header", required=True),
    OpenApiParameter("X-Signature", str, location="header", required=True,
                     description="HMAC-SHA256 of method, full path, timestamp, optional nonce and raw body."),
    OpenApiParameter("X-Nonce", str, location="header",
                     description="Required when nonce enforcement is enabled."),
]
PAGE_PARAMETERS = HMAC_PARAMETERS + [
    OpenApiParameter("cursor", str, description="Opaque, signed continuation cursor."),
    OpenApiParameter("page_size", int, description="1–200; default 100."),
]
READ_ERRORS = {code: OpenApiResponse(ErrorSerializer, description=description)
               for code, description in (
    (400, "Invalid cursor or page size."), (401, "Missing or invalid HMAC signature."),
    (403, "Server type, tenant binding or required scopes missing."),
    (404, "Tenant/subject/module/feature unavailable."), (429, "Read rate exceeded."),
    (423, "Source tenant is frozen; audited reads cannot append history."),
    (503, "Source gate could not be proven available."),
)}
