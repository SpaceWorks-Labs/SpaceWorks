"""WP4 detail surface, independent of WP2's original public machine list."""

from drf_spectacular.utils import extend_schema
from rest_framework import generics
from rest_framework.exceptions import ValidationError
from rest_framework.permissions import AllowAny

from apps.apiclients.throttling import ClientTierRateThrottle
from apps.accounts import rbac
from apps.hardware_requests.exceptions import ErrorSerializer
from apps.makerspaces.editions import require_public_surface
from apps.makerspaces.guards import require_module_for_servable
from apps.makerspaces.lookup import get_public_makerspace
from apps.makerspaces.platform import feature_enabled
from apps.openapi import PUBLIC_API_AUTH_PARAMETERS
from .models import Machine
from .serializers_public_detail import PublicMachineDetailSerializer


ERRORS = {code: ErrorSerializer for code in (400, 401, 403, 404, 429)}


class PublicMachineDetailMixin:
    permission_classes = [AllowAny]
    throttle_classes = [ClientTierRateThrottle]
    throttle_scope = "public_read"
    serializer_class = PublicMachineDetailSerializer

    def get_queryset(self):
        space = get_public_makerspace(self.kwargs["makerspace_slug"])
        require_public_surface("machines")
        require_module_for_servable(space, "machines")
        if not feature_enabled(space, "machines.public_detail"):
            from apps.makerspaces.guards import feature_off
            raise feature_off("machines.public_detail", "Public machine details are turned off.")
        if not getattr(space, "public_site_enabled", space.public_inventory_enabled):
            raise ValidationError({"detail": "Public site is disabled."})
        return rbac.scope_public_catalogue(
            Machine.objects.select_related("machine_type", "makerspace"), space,
        ).filter(is_public=True, is_active=True).order_by("name", "pk")


    def get_serializer(self, *args, **kwargs):
        from .public_detail import queue_summaries
        instance = args[0] if args else None
        if instance is not None:
            rows = list(instance) if kwargs.get("many") else [instance]
            kwargs.setdefault("context", self.get_serializer_context())
            kwargs["context"]["queue_summaries"] = queue_summaries(rows)
        return super().get_serializer(*args, **kwargs)


class PublicMachineDetailView(PublicMachineDetailMixin, generics.RetrieveAPIView):
    @extend_schema(request=None, auth=[], parameters=PUBLIC_API_AUTH_PARAMETERS, responses={200: PublicMachineDetailSerializer, **ERRORS})
    def get(self, request, *args, **kwargs):
        return super().get(request, *args, **kwargs)


class PublicMachineDetailListView(PublicMachineDetailMixin, generics.ListAPIView):
    @extend_schema(request=None, auth=[], parameters=PUBLIC_API_AUTH_PARAMETERS, responses={200: PublicMachineDetailSerializer(many=True), **ERRORS})
    def get(self, request, *args, **kwargs):
        return super().get(request, *args, **kwargs)
