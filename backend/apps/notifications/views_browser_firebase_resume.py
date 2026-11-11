"""Read-only ownership recheck before restoring a suspended browser-push ticket."""
from drf_spectacular.utils import extend_schema
from rest_framework import serializers
from rest_framework.response import Response

from apps.makerspaces.telemetry_schema import StrictSerializer
from apps.openapi_errors import errors
from .models_browser_firebase import BrowserFirebaseInstallation, BrowserFirebaseRegistration
from .views_browser_firebase import Base
from .browser_firebase_throttles import BrowserFirebaseReadThrottle


class ResumeCheckRequest(StrictSerializer):
    owner_epoch = serializers.UUIDField()


class ResumeCheckResult(serializers.Serializer):
    may_resume = serializers.BooleanField()


class BrowserFirebaseResumeView(Base):
    throttle_classes = [BrowserFirebaseReadThrottle]
    # Explicit ID: the auto name collides with the global may-resume check (`_create_2`).
    @extend_schema(operation_id="api_v1_notifications_browser_firebase_space_may_resume_create",
                   tags=["Personal notifications"], request=ResumeCheckRequest,
                   responses={200: ResumeCheckResult, **errors(400, 401, 403, 404, 429)})
    def post(self, request, makerspace_id):
        space = self.space(request, makerspace_id)
        data = ResumeCheckRequest(data=request.data)
        data.is_valid(raise_exception=True)
        owners = BrowserFirebaseInstallation.objects.filter(user=request.user, owner_epoch=data.validated_data["owner_epoch"])
        allowed = BrowserFirebaseRegistration.objects.filter(
            makerspace=space, user=request.user, active=True, revoked_at__isnull=True,
            fid_hmac__in=owners.values("fid_hmac"),
        ).exists()
        response = Response({"may_resume": allowed})
        response["Cache-Control"] = "no-store"
        return response
