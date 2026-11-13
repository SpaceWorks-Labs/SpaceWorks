from django.db import transaction
from django.shortcuts import get_object_or_404
from drf_spectacular.utils import extend_schema
from rest_framework import serializers
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.accounts import rbac
from apps.admin_api.permissions import IsActiveStaff
from apps.audit.services import record
from apps.hardware_requests.exceptions import ErrorSerializer
from .models import Makerspace
from .website_origins import validate_origins


class WebsiteOriginsSerializer(serializers.Serializer):
    origins = serializers.ListField(child=serializers.CharField(max_length=255), max_length=20)

    def validate_origins(self, value):
        return validate_origins(value)


class WebsiteOriginsView(APIView):
    permission_classes = [IsActiveStaff]

    def space(self, request, makerspace_id):
        rows = rbac.scope_by_visibility_or_action(request.user, rbac.Action.MANAGE_MAKERSPACE, Makerspace.objects.all(), field="pk")
        space = get_object_or_404(rows, pk=makerspace_id)
        if not rbac.can(request.user, rbac.Action.MANAGE_MAKERSPACE, space.pk):
            from rest_framework.exceptions import PermissionDenied
            raise PermissionDenied()
        return space

    @extend_schema(tags=["Public websites"], responses={200: WebsiteOriginsSerializer, **{code: ErrorSerializer for code in (401, 403, 404)}})
    def get(self, request, makerspace_id):
        return Response({"origins": self.space(request, makerspace_id).website_embed_origins})

    @extend_schema(tags=["Public websites"], request=WebsiteOriginsSerializer, responses={200: WebsiteOriginsSerializer, **{code: ErrorSerializer for code in (400, 401, 403, 404)}})
    @transaction.atomic
    def put(self, request, makerspace_id):
        space = self.space(request, makerspace_id)
        from apps.tenant_migration.gate_runtime import assert_write_allowed
        assert_write_allowed(space.pk)
        data = WebsiteOriginsSerializer(data=request.data)
        data.is_valid(raise_exception=True)
        space = Makerspace.objects.select_for_update().get(pk=space.pk)
        self.space(request, space.pk)
        space.website_embed_origins = data.validated_data["origins"]
        space.save(update_fields=["website_embed_origins", "updated_at"])
        record(actor=request.user, makerspace=space, action="makerspace.website_origins_updated",
               target=space, meta={"count": len(space.website_embed_origins)})
        return Response(data.validated_data)
