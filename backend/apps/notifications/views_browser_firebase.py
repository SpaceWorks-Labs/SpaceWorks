"""Authenticated, tenant-scoped FID possession proof; native device grants are refused (403)."""
from drf_spectacular.utils import extend_schema
from rest_framework import serializers
from rest_framework.exceptions import NotFound
from rest_framework.response import Response
from rest_framework.throttling import UserRateThrottle
from rest_framework.views import APIView

from apps.integrations.firebase_web_config import effective
from apps.integrations.models_push import PlatformPushSettings
from apps.integrations.push_fcm import PushProviderError
from apps.makerspaces.platform import feature_enabled
from apps.openapi_errors import errors
from .browser_firebase_permissions import IsBrowserSession
from .access import personal_space
from . import browser_firebase_challenge as proof
from .models_browser_firebase import BrowserFirebaseInstallation, BrowserFirebaseRegistration
from apps.audit.services import record
from apps.tenant_migration.gate_runtime import tenant_write
from django.utils import timezone
from django.db import transaction
from apps.makerspaces.models import Makerspace
from django.utils.translation import gettext


class FirebaseThrottle(UserRateThrottle):
    scope = "browser-firebase"

    def get_rate(self):
        return "10/hour"


class BeginSerializer(serializers.Serializer):
    project_id = serializers.RegexField(r"^[a-z0-9-]{6,63}$")
    fid = serializers.RegexField(r"^[A-Za-z0-9_-]{11,256}$")


class ChallengeSerializer(BeginSerializer):
    challenge_id = serializers.UUIDField()


class StartedSerializer(serializers.Serializer):
    challenge = serializers.CharField()


class ConfirmSerializer(serializers.Serializer):
    project_id = serializers.RegexField(r"^[a-z0-9-]{6,63}$")
    fid = serializers.RegexField(r"^[A-Za-z0-9_-]{11,256}$")
    challenge = serializers.UUIDField()
    nonce = serializers.RegexField(r"^[A-Za-z0-9_-]{40,64}$")


class ConfirmedSerializer(serializers.Serializer):
    owner_epoch = serializers.UUIDField()


class Base(APIView):
    permission_classes = [IsBrowserSession]
    throttle_classes = [FirebaseThrottle]

    def space(self, request, makerspace_id):
        space = personal_space(request.user, makerspace_id)
        if not feature_enabled(space, "notifications.web_push"):
            raise NotFound()
        return space


class BrowserFirebaseBeginView(Base):
    @extend_schema(tags=["Personal notifications"], request=ChallengeSerializer,
                   responses={200: StartedSerializer, **errors(400, 401, 403, 404, 429, 503)})
    def post(self, request, makerspace_id):
        space = self.space(request, makerspace_id)
        data = ChallengeSerializer(data=request.data)
        data.is_valid(raise_exception=True)
        settings_row = PlatformPushSettings.objects.first()
        if not settings_row or not settings_row.fcm_configured:
            raise NotFound()
        state = effective(settings_row)
        if not state["configured"] or state["config"]["project_id"] != data.validated_data["project_id"]:
            raise NotFound()
        try:
            result = proof.begin(actor=request.user, space=space, project=data.validated_data["project_id"],
                                 fid=data.validated_data["fid"], challenge=str(data.validated_data["challenge_id"]),
                                 push_settings=settings_row)
        except PushProviderError:
            return Response({"detail": gettext("Firebase challenge delivery is unavailable.")}, status=503)
        record(request.user, "notification.browser_firebase_challenge_started", makerspace=space, target=space)
        response = Response(result)
        response["Cache-Control"] = "no-store"
        return response

    @extend_schema(tags=["Personal notifications"], request=BeginSerializer,
                   responses={204: None, **errors(400, 401, 403, 404, 429)})
    def delete(self, request, makerspace_id):
        space = self.space(request, makerspace_id)
        data = BeginSerializer(data=request.data)
        data.is_valid(raise_exception=True)
        project, fid = data.validated_data["project_id"], data.validated_data["fid"]
        with tenant_write(space.pk), transaction.atomic():
            Makerspace.objects.select_for_update().get(pk=space.pk)
            identity = proof._mac("fid", project, fid)
            BrowserFirebaseInstallation.objects.select_for_update().filter(fid_hmac=identity).first()
            BrowserFirebaseRegistration.objects.filter(
                makerspace=space, user=request.user, project_id=project,
                fid_hmac=identity, active=True,
            ).update(active=False, revoked_at=timezone.now())
            record(request.user, "notification.browser_firebase_unsubscribed", makerspace=space, target=space)
        return Response(status=204)


class BrowserFirebaseConfirmView(Base):
    @extend_schema(tags=["Personal notifications"], request=ConfirmSerializer,
                   responses={200: ConfirmedSerializer, **errors(400, 401, 403, 404, 429)})
    def post(self, request, makerspace_id):
        space = self.space(request, makerspace_id)
        data = ConfirmSerializer(data=request.data)
        data.is_valid(raise_exception=True)
        state = effective(PlatformPushSettings.objects.first())
        if not state["configured"] or state["config"]["project_id"] != data.validated_data["project_id"]:
            raise NotFound()
        result = proof.confirm(actor=request.user, space=space, project=data.validated_data["project_id"],
                      fid=data.validated_data["fid"],
                      challenge=str(data.validated_data["challenge"]), nonce=data.validated_data["nonce"])
        response = Response(result)
        response["Cache-Control"] = "no-store"
        return response
