"""Server integration reads, shared by separable domain adapters.

Register typed targets at app startup; this module never imports a domain app.
"""

from django.utils.translation import gettext
from dataclasses import dataclass

from django.apps import apps
from django.conf import settings
from django.core import signing
from rest_framework import serializers
from rest_framework.exceptions import AuthenticationFailed, PermissionDenied
from rest_framework.permissions import BasePermission
from rest_framework.throttling import SimpleRateThrottle
from rest_framework.views import APIView

from apps.makerspaces.servability import is_servable


@dataclass(frozen=True)
class ReadTarget:
    model_label: str | None = None
    id_kwarg: str = "pk"
    tenant_path: str = "makerspace"


_targets: dict[str, ReadTarget] = {}


def register_read_target(view_name, target):
    """Idempotent, query-free registration from a live domain's ready hook."""
    previous = _targets.get(view_name)
    if previous is not None and previous != target:
        raise ValueError(f"Conflicting API read target: {view_name}")
    _targets[view_name] = target


def read_target_registered(view_name):
    return view_name in _targets


def resolve_read_target(request, match):
    from apps.apiclients.models import ApiClient
    adapter = _targets.get(match.view_name)
    if adapter is None:
        return None, False
    client = ApiClient.objects.select_related("makerspace").filter(
        client_id=request.headers.get("X-Client-Id", ""),
        client_type="server", is_active=True, makerspace__isnull=False,
    ).first()
    if client is None:
        return None, False
    tenant = client.makerspace
    if not is_servable(tenant):
        return None, False
    if adapter.model_label:
        model = apps.get_model(adapter.model_label)
        # Resolve the ID AND tenant in the same predicate. A foreign/malformed ID
        # has exactly the same unresolved outcome as a missing one.
        if not model.objects.filter(**{
            "pk": match.kwargs.get(adapter.id_kwarg),
            f"{adapter.tenant_path}_id": tenant.pk,
        }).exists():
            return None, False
    return tenant, True


class SignedServerReadPermission(BasePermission):
    def has_permission(self, request, view):
        client = getattr(request, "api_client", None)
        if not getattr(request, "api_client_signature_verified", False) or client is None:
            raise AuthenticationFailed(gettext("A verified server signature is required."))
        if client.client_type != "server" or client.makerspace_id is None:
            raise PermissionDenied(gettext("A tenant-bound server client is required."))
        if not set(view.required_scopes).issubset(client.scopes):
            raise PermissionDenied(gettext("Required integration scopes are missing."))
        from apps.apiclients.scope_registry import classify
        if not classify(request, client).verdict:
            raise PermissionDenied(gettext("This API target is unavailable."))
        return True


class ServerReadThrottle(SimpleRateThrottle):
    scope = "integration_read"

    def get_rate(self):
        return getattr(settings, "INTEGRATION_READ_RATE", "120/min")

    def get_cache_key(self, request, view):
        client = getattr(request, "api_client", None)
        return self.cache_format % {"scope": self.scope,
                                    "ident": client.pk if client else self.get_ident(request)}


class SignedReadView(APIView):
    authentication_classes = []
    permission_classes = [SignedServerReadPermission]
    throttle_classes = [ServerReadThrottle]
    http_method_names = ["get", "head", "options"]
    required_scopes = ()

    def finalize_response(self, request, response, *args, **kwargs):
        response = super().finalize_response(request, response, *args, **kwargs)
        response["Cache-Control"] = "private, no-store"
        response["Referrer-Policy"] = "no-referrer"
        return response


class KeysetQuerySerializer(serializers.Serializer):
    cursor = serializers.CharField(max_length=2048, required=False)
    page_size = serializers.IntegerField(min_value=1, max_value=200, default=100)


def keyset_page(request, queryset, *, subject):
    """Signed cursor binds the monotonic PK to client, tenant and subject."""
    query = KeysetQuerySerializer(data=request.query_params)
    query.is_valid(raise_exception=True)
    size = query.validated_data["page_size"]
    client = request.api_client
    binding = [client.pk, client.makerspace_id, subject]
    cursor = query.validated_data.get("cursor")
    if cursor:
        try:
            decoded = signing.loads(cursor, salt="api-read-keyset.v1", max_age=86400)
            if decoded["binding"] != binding or type(decoded["after"]) is not int:
                raise ValueError()
            queryset = queryset.filter(pk__gt=decoded["after"])
        except (signing.BadSignature, ValueError, KeyError, TypeError):
            raise serializers.ValidationError({"cursor": gettext("Invalid or expired cursor.")}) from None
    rows = list(queryset.order_by("pk")[:size + 1])
    next_cursor = None
    if len(rows) > size:
        next_cursor = signing.dumps({"binding": binding, "after": rows[size - 1].pk},
                                    salt="api-read-keyset.v1", compress=True)
    return rows[:size], next_cursor
