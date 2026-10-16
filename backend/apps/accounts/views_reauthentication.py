"""Authenticated, throttled session step-up; refresh never calls these services."""

from drf_spectacular.utils import extend_schema
from rest_framework.exceptions import PermissionDenied
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.throttling import SimpleRateThrottle
from rest_framework.views import APIView

from apps.accounts import mfa_policy, reauthentication as services, reauthentication_intents as intents
from apps.accounts.serializers_reauthentication import (
    EmptySerializer, ReauthenticationEmailConfirmSerializer, ReauthenticationEmailConfirmedSerializer,
    ReauthenticationEmailSentSerializer, ReauthenticationResultSerializer, ReauthenticationSerializer,
    ReauthenticationSocialCompleteSerializer, ReauthenticationSocialStartSerializer,
    ReauthenticationSocialStartedSerializer, ReauthenticationStatusSerializer,
    ReauthenticationFactorSerializer, ReauthenticationPhoneStartedSerializer,
)
from apps.openapi_errors import errors

ERRORS = errors(400, 401, 403, 429, 503)


class ReauthenticationThrottle(SimpleRateThrottle):
    scope = "recent_reauthentication"
    rate = "6/min"

    def get_cache_key(self, request, view):
        return self.cache_format % {"scope": self.scope, "ident": request.user.pk}


def validated(cls, request):
    serializer = cls(data=request.data)
    serializer.is_valid(raise_exception=True)
    return serializer.validated_data


def response(data):
    result = Response(data)
    result["Cache-Control"] = "private, no-store"
    result["Referrer-Policy"] = "no-referrer"
    return result


class ReauthenticationView(APIView):
    permission_classes = [IsAuthenticated]
    throttle_classes = [ReauthenticationThrottle]

    @extend_schema(tags=["Reauthentication"], responses={200: ReauthenticationStatusSerializer, **ERRORS})
    def get(self, request):
        services.binding(request)
        verified = True
        try:
            services.require_recent_reauth(request)
        except PermissionDenied:
            verified = False
        credential = mfa_policy.credential(request.user)
        return response({"verified": verified, "password_available": request.user.has_usable_password(),
                         "mfa_enabled": bool(credential and credential.enabled_at),
                         "providers": list(request.user.social_identities.values_list("provider", flat=True))})

    @extend_schema(tags=["Reauthentication"], request=ReauthenticationSerializer,
                   responses={200: ReauthenticationResultSerializer, **ERRORS})
    def post(self, request):
        return response(services.verify(request, **validated(ReauthenticationSerializer, request)))


class ReauthenticationSocialStartView(ReauthenticationView):
    http_method_names = ["post", "options"]

    @extend_schema(tags=["Reauthentication"], request=ReauthenticationSocialStartSerializer,
                   responses={200: ReauthenticationSocialStartedSerializer, **ERRORS})
    def post(self, request):
        return response(intents.start_social(request, **validated(ReauthenticationSocialStartSerializer, request)))


class ReauthenticationSocialCompleteView(ReauthenticationView):
    http_method_names = ["post", "options"]

    @extend_schema(tags=["Reauthentication"], request=ReauthenticationSocialCompleteSerializer,
                   responses={200: ReauthenticationResultSerializer, **ERRORS})
    def post(self, request):
        return response(intents.complete_social(request, **validated(ReauthenticationSocialCompleteSerializer, request)))


class ReauthenticationEnrollmentEmailView(ReauthenticationView):
    http_method_names = ["post", "options"]

    @extend_schema(tags=["Reauthentication"], request=EmptySerializer,
                   responses={200: ReauthenticationEmailSentSerializer, **ERRORS})
    def post(self, request):
        validated(EmptySerializer, request)
        return response(intents.start_email(request))


class ReauthenticationEnrollmentConfirmView(ReauthenticationView):
    http_method_names = ["post", "options"]

    @extend_schema(tags=["Reauthentication"], request=ReauthenticationEmailConfirmSerializer,
                   responses={200: ReauthenticationEmailConfirmedSerializer, **ERRORS})
    def post(self, request):
        return response(intents.confirm_email(request, **validated(ReauthenticationEmailConfirmSerializer, request)))


class ReauthenticationSocialFactorView(ReauthenticationView):
    http_method_names = ["post", "options"]

    @extend_schema(tags=["Reauthentication"], request=ReauthenticationFactorSerializer,
                   responses={200: ReauthenticationResultSerializer, **ERRORS})
    def post(self, request):
        from apps.accounts.reauthentication_factors import confirm_factor
        return response(confirm_factor(request, **validated(ReauthenticationFactorSerializer, request)))


class ReauthenticationPhoneStartView(ReauthenticationView):
    http_method_names = ["post", "options"]

    @extend_schema(tags=["Reauthentication"], request=EmptySerializer,
                   responses={200: ReauthenticationPhoneStartedSerializer, **ERRORS})
    def post(self, request):
        from apps.accounts.reauthentication_phone import start
        validated(EmptySerializer, request)
        return response(start(request))


class ReauthenticationPhoneConfirmView(ReauthenticationView):
    http_method_names = ["post", "options"]

    @extend_schema(tags=["Reauthentication"], request=ReauthenticationFactorSerializer,
                   responses={200: ReauthenticationResultSerializer, **ERRORS})
    def post(self, request):
        from apps.accounts.reauthentication_phone import confirm
        return response(confirm(request, **validated(ReauthenticationFactorSerializer, request)))
