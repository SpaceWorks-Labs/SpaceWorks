from drf_spectacular.utils import OpenApiResponse
from apps.hardware_requests.exceptions import ErrorSerializer

ERRORS = {
    400: OpenApiResponse(ErrorSerializer, description="Invalid input, preset, project or location."),
    401: OpenApiResponse(description="Authentication required."),
    403: OpenApiResponse(ErrorSerializer, description="Account, origin or tenant permission refused."),
    404: OpenApiResponse(description="Makerspace or presence module unavailable."),
    423: OpenApiResponse(ErrorSerializer, description="Tenant migration source is frozen."),
    429: OpenApiResponse(description="Rate limit exceeded."),
    503: OpenApiResponse(ErrorSerializer, description="Tenant is frozen or not restored."),
}
