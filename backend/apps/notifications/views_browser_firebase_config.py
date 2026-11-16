from drf_spectacular.utils import extend_schema
from rest_framework.exceptions import NotFound
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.integrations.firebase_web_config import FirebaseWebStateSerializer, effective
from apps.integrations.models_push import PlatformPushSettings
from apps.makerspaces.platform import feature_enabled
from apps.openapi_errors import errors
from .browser_firebase_permissions import IsBrowserSession
from .access import personal_space
from .browser_firebase_throttles import BrowserFirebaseReadThrottle


class BrowserFirebaseConfigView(APIView):
    permission_classes = [IsBrowserSession]
    throttle_classes = [BrowserFirebaseReadThrottle]

    @extend_schema(tags=["Personal notifications"], responses={200: FirebaseWebStateSerializer, **errors(401, 403, 404, 429)})
    def get(self, request, makerspace_id):
        space = personal_space(request.user, makerspace_id)
        if not feature_enabled(space, "notifications.web_push"):
            raise NotFound()
        response = Response(effective(PlatformPushSettings.objects.filter(pk=1).first()))
        response["Cache-Control"] = "no-store"
        return response
