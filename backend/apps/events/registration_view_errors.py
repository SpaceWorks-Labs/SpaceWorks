"""Shared registration error schemas, without a circular view-module dependency."""

from drf_spectacular.utils import OpenApiResponse

from apps.hardware_requests.exceptions import ErrorSerializer
from .views_admin_event_detail import EVENT_ERROR_409, EVENT_VALIDATION_ERROR_SCHEMA

REGISTRATION_ACTION_ERRORS = {
    400: OpenApiResponse(EVENT_VALIDATION_ERROR_SCHEMA, description="Unexpected request body or events module disabled."),
    401: OpenApiResponse(ErrorSerializer, description="Authentication is required."),
    403: OpenApiResponse(ErrorSerializer, description="Event management is required."),
    404: OpenApiResponse(ErrorSerializer, description="Registration not found."),
    409: EVENT_ERROR_409,
}
