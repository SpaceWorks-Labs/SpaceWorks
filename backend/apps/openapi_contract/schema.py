"""The project schema class (REST_FRAMEWORK["DEFAULT_SCHEMA_CLASS"]).

Only what a view leaves unsaid is filled, and only from what its own configuration
already decides; an `extend_schema(...)` on the view always wins, because the decorator
subclasses this class and answers before it is consulted.
"""
from django.conf import settings
from drf_spectacular.openapi import AutoSchema
from drf_spectacular.utils import OpenApiResponse
from rest_framework import permissions

from apps.openapi_errors import _DESCRIPTIONS

from .component_names import COMPONENT_NAMES
from .registry import contract_marks
from .tags import fallback_tag

#: The three API-client credential shapes (docs/api-client-protocol.md), as alternatives.
CLIENT_SCHEMES = ({"ServerHMAC": []}, {"BrowserClient": []}, {"PublishableKey": []})
_WRITE_METHODS = frozenset({"POST", "PUT", "PATCH"})


def protected_path(path):
    from apps.apiclients.read_prefixes import mandatory_hmac_prefixes
    prefixes = (*settings.HMAC_PROTECTED_PATH_PREFIXES, *mandatory_hmac_prefixes())
    return path.startswith(tuple(prefixes))


class SpaceWorksAutoSchema(AutoSchema):
    def get_serializer_name(self, serializer, direction):
        cls = type(serializer)
        return COMPONENT_NAMES.get(f"{cls.__module__}.{cls.__qualname__}") or super().get_serializer_name(
            serializer, direction)

    def get_tags(self):
        tag = fallback_tag(self.path)
        return [tag] if tag else super().get_tags()

    def get_operation(self, path, path_regex, path_prefix, method, registry):
        operation = super().get_operation(path, path_regex, path_prefix, method, registry)
        if operation is None:
            return None
        operation["security"] = self._security(operation.get("security"))
        cls = self.view.__class__
        marks = contract_marks(f"{cls.__module__}.{cls.__qualname__}", self.method)
        payload = marks.get("x-free-form", {}).get("request")
        if payload and "requestBody" not in operation:
            operation["requestBody"] = {"content": {"application/json": {"schema": {
                "type": "object", "additionalProperties": True, "description": payload,
            }}}}
        operation.update(marks)
        return operation

    def _security(self, security):
        # No requirement (no authenticator, or an explicit `auth=[]`) means anonymous: say so.
        security = list(security or [{}])
        if protected_path(self.path) and {} in security and not any("ServerHMAC" in a for a in security):
            # A public API route: anonymous until API_CLIENT_AUTH_REQUIRED, and any client
            # credential identifies the caller for scopes and rate limits.
            security = [a for a in security if a != {}] + [dict(a) for a in CLIENT_SCHEMES] + [{}]
        return security

    def _get_response_bodies(self, direction="response"):
        responses = super()._get_response_bodies(direction)
        if direction != "response" or any(str(code)[:1] in "45" for code in responses):
            return responses
        from apps.hardware_requests.exceptions import ErrorSerializer
        for code in self._derived_error_codes():
            responses[str(code)] = self._get_response_for_code(
                OpenApiResponse(ErrorSerializer, description=_DESCRIPTIONS[code]), str(code),
                direction=direction,
            )
        return responses

    def _derived_error_codes(self):
        """The errors this view's own configuration can answer with."""
        perms = [type(p) for p in self.view.get_permissions()]
        open_route = all(p is permissions.AllowAny for p in perms)
        codes = []
        if self.method in _WRITE_METHODS:
            codes.append(400)
        if not open_route:
            if self.view.get_authenticators():
                codes.append(401)
            codes.append(403)
        if "{" in self.path:
            codes.append(404)
        try:
            throttled = bool(self.view.get_throttles())
        except Exception:  # a misconfigured throttle fails at request time, not here
            throttled = False
        if throttled:
            codes.append(429)
        return codes or [500]
