"""Read-only installation-owner check, independent of individual space state."""
from drf_spectacular.utils import extend_schema
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.accounts.models import User
from apps.openapi_errors import errors
from .browser_firebase_permissions import IsBrowserSession
from .models_browser_firebase import BrowserFirebaseInstallation
from .browser_firebase_throttles import BrowserFirebaseReadThrottle
from .views_browser_firebase_resume import ResumeCheckRequest, ResumeCheckResult


class BrowserFirebaseGlobalResumeView(APIView):
    permission_classes = [IsBrowserSession]
    throttle_classes = [BrowserFirebaseReadThrottle]

    @extend_schema(operation_id="api_v1_notifications_browser_firebase_may_resume_create",
                   tags=["Personal notifications"], request=ResumeCheckRequest,
                   responses={200: ResumeCheckResult, **errors(400, 401, 403, 429)})
    def post(self, request):
        data = ResumeCheckRequest(data=request.data)
        data.is_valid(raise_exception=True)
        user = request.user
        active = (getattr(user, "is_active", False)
                  and getattr(user, "access_status", None) == User.AccessStatus.ACTIVE
                  and not getattr(user, "is_tenant_dump_stub", False)
                  and not getattr(user, "must_change_password", False))
        allowed = active and BrowserFirebaseInstallation.objects.filter(
            user=user, owner_epoch=data.validated_data["owner_epoch"]).exists()
        response = Response({"may_resume": bool(allowed)})
        response["Cache-Control"] = "no-store"
        return response
