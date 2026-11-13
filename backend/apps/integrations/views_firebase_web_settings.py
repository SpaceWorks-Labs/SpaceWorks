from django.db import transaction
from drf_spectacular.utils import extend_schema
from rest_framework.exceptions import ValidationError
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.accounts.reauthentication_permissions import RecentReauthenticationMixin
from apps.admin_api.permissions import IsActiveSuperAdmin
from apps.audit.services import record
from apps.openapi_errors import errors
from .firebase_web_config import FirebaseWebStateSerializer, FirebaseWebWriteSerializer, effective, service_project
from .models_push import PlatformPushSettings
from django.utils.translation import gettext


class PlatformFirebaseWebSettingsView(RecentReauthenticationMixin, APIView):
    permission_classes = [IsActiveSuperAdmin]

    @extend_schema(tags=["Platform providers"], responses={200: FirebaseWebStateSerializer, **errors(401, 403)})
    def get(self, request):
        response = Response(effective(PlatformPushSettings.objects.filter(pk=1).first()))
        response["Cache-Control"] = "no-store"
        return response

    @extend_schema(tags=["Platform providers"], request=FirebaseWebWriteSerializer,
                   responses={200: FirebaseWebStateSerializer, **errors(400, 401, 403)})
    def patch(self, request):
        data = FirebaseWebWriteSerializer(data=request.data)
        data.is_valid(raise_exception=True)
        value = data.validated_data["config"]
        with transaction.atomic():
            PlatformPushSettings.objects.get_or_create(pk=1)
            row = PlatformPushSettings.objects.select_for_update().get(pk=1)
            if value is not None and service_project(row) != value["project_id"]:
                raise ValidationError({"config": gettext("Firebase web project must match the platform push credential.")})
            row.firebase_web_config = value or {}
            row.save(update_fields=["firebase_web_config", "updated_at"])
            record(request.user, "platform.firebase_web_settings_updated", target=row,
                   meta={"fields": ["firebase_web_config"], "configured": bool(value)})
        response = Response(effective(row))
        response["Cache-Control"] = "no-store"
        return response
