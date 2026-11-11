"""App connections (#196): the consent API behind the console's consent screen, and Connected apps.

The authorization endpoint a third-party app sends the browser to is
`/api/v1/oauth/authorize/`; it redirects to the console consent screen, which calls
`GET` here to show the app and scopes and `POST` (after a fresh re-authentication) to
answer. django-oauth-toolkit validates the request (client, redirect URI, PKCE) and mints
the code; this view only adds the signed-in person and records the consent.
"""
from django.db import transaction
from django.shortcuts import get_object_or_404
from django.utils.translation import gettext
from drf_spectacular.utils import OpenApiParameter, extend_schema
from oauth2_provider.models import get_access_token_model, get_application_model, get_grant_model, \
    get_refresh_token_model
from oauth2_provider.exceptions import OAuthToolkitError
from oauth2_provider.oauth2_backends import get_oauthlib_core
from oauthlib.oauth2 import OAuth2Error
from rest_framework import serializers, status
from rest_framework.exceptions import ValidationError
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.throttling import ScopedRateThrottle
from rest_framework.views import APIView

from apps.accounts.reauthentication_permissions import RecentReauthenticationMixin
from apps.audit import services as audit
from apps.openapi_errors import errors

from . import person_scopes
from .models_tokens import OAuthConsent
from .views_tokens import MFA_CLAIM_KEYS, require_person

TAGS = ["App connections"]
CREDENTIAL_KEYS = ("client_id", "redirect_uri", "response_type", "state", "code_challenge",
                   "code_challenge_method", "nonce", "claims")
OAUTH_PARAMETERS = [OpenApiParameter(name, str) for name in (
    "client_id", "redirect_uri", "response_type", "scope", "state", "code_challenge", "code_challenge_method")]


class ConsentScopeSerializer(serializers.Serializer):
    value = serializers.CharField()
    label = serializers.CharField()
    description = serializers.CharField()


class ConsentPreviewSerializer(serializers.Serializer):
    app_name = serializers.CharField()
    space_name = serializers.CharField()
    redirect_uri = serializers.CharField()
    scopes = ConsentScopeSerializer(many=True)


class ConsentDecisionSerializer(serializers.Serializer):
    allow = serializers.BooleanField()


class ConsentRedirectSerializer(serializers.Serializer):
    redirect_to = serializers.CharField(help_text="Send the browser here: the app's redirect URI with a code or error.")


class ConnectedAppSerializer(serializers.Serializer):
    application_id = serializers.IntegerField(source="application.pk")
    app_name = serializers.CharField(source="application.name")
    space_name = serializers.CharField(source="application.spaceworks_registration.makerspace.name")
    scopes = serializers.ListField(child=serializers.CharField())
    granted_at = serializers.DateTimeField()


def _validated(request):
    try:
        scopes, info = get_oauthlib_core().validate_authorization_request(request._request)
    except OAuth2Error as exc:
        raise ValidationError({"detail": getattr(error, "description", None) or getattr(error, "error", "invalid_request")}) from exc
    except Exception as exc:  # DOT wraps invalid client/redirect as its own fatal error type
        raise ValidationError({"detail": gettext("This app request is not valid.")}) from exc
    # oauthlib also accepts the "plain" method (and assumes it when none is named), where the
    # challenge IS the verifier; only S256 is offered, so refuse anything else.
    if info.get("code_challenge_method") != "S256":
        raise ValidationError({"detail": gettext("Use PKCE with code_challenge_method=S256.")})
    application = get_application_model().objects.select_related("spaceworks_registration__makerspace").get(
        client_id=info["client_id"])
    return scopes, {key: info[key] for key in CREDENTIAL_KEYS if info.get(key)}, application


class ConsentView(RecentReauthenticationMixin, APIView):
    permission_classes = [IsAuthenticated]
    throttle_classes = [ScopedRateThrottle]
    throttle_scope = "oauth_consent"

    @extend_schema(tags=TAGS, summary="What an app is asking for (the consent screen)", parameters=OAUTH_PARAMETERS,
                   responses={200: ConsentPreviewSerializer, **errors(400, 401, 403, 429)})
    def get(self, request):
        require_person(request.user)
        scopes, credentials, application = _validated(request)
        labels = {row["value"]: row for row in person_scopes.catalog()}
        return Response({"app_name": application.name,
                         "space_name": application.spaceworks_registration.makerspace.name,
                         "redirect_uri": credentials["redirect_uri"],
                         "scopes": [{"value": scope, "label": labels.get(scope, {}).get("label", scope),
                                     "description": labels.get(scope, {}).get("description", "")} for scope in scopes]})

    @extend_schema(tags=TAGS, summary="Allow or deny the app (needs a recent re-authentication)",
                   parameters=OAUTH_PARAMETERS, request=ConsentDecisionSerializer,
                   responses={200: ConsentRedirectSerializer, **errors(400, 401, 403, 429)})
    def post(self, request):
        require_person(request.user)
        decision = ConsentDecisionSerializer(data=request.data)
        decision.is_valid(raise_exception=True)
        scopes, credentials, application = _validated(request)
        registration = application.spaceworks_registration
        if set(scopes) & person_scopes.STAFF_SCOPES:
            from apps.accounts.staff_identity import has_staff_role
            if not has_staff_role(request.user, registration.makerspace_id):
                raise ValidationError({"detail": gettext("This app asks for staff access in a space where you hold no role.")})
        allow = decision.validated_data["allow"]
        with transaction.atomic():
            if allow:
                claims = {key: request.auth.get(key) for key in MFA_CLAIM_KEYS if hasattr(request.auth, "get")}
                OAuthConsent.objects.update_or_create(user=request.user, application=application,
                                                      defaults={"scopes": list(scopes), "mfa_claims": claims})
                audit.record(request.user, "oauth_consent.granted", makerspace=registration.makerspace,
                             target=application, meta={"scopes": list(scopes)})
            try:
                uri, _headers, _body, _status = get_oauthlib_core().create_authorization_response(
                    request._request, scopes, credentials, allow)
            except (OAuth2Error, OAuthToolkitError) as exc:
                # django-oauth-toolkit wraps a refusal (a denied consent) in OAuthToolkitError.
                error = getattr(exc, "oauthlib_error", None) or exc
                uri = error.in_uri(credentials["redirect_uri"]) if not allow else None
                if uri is None:
                    raise ValidationError({"detail": getattr(error, "description", None) or getattr(error, "error", "invalid_request")}) from exc
        return Response({"redirect_to": uri})


class ConnectedAppListView(APIView):
    permission_classes = [IsAuthenticated]

    @extend_schema(tags=TAGS, summary="Apps I have connected", responses={200: ConnectedAppSerializer(many=True),
                                                                         **errors(401, 403)})
    def get(self, request):
        require_person(request.user)
        rows = OAuthConsent.objects.filter(user=request.user).select_related(
            "application__spaceworks_registration__makerspace").order_by("-granted_at")
        return Response(ConnectedAppSerializer(rows, many=True).data)


def disconnect(user, application):
    """Drop a person's consent and every token, refresh token and code the app holds for them."""
    get_refresh_token_model().objects.filter(user=user, application=application).delete()
    get_access_token_model().objects.filter(user=user, application=application).delete()
    get_grant_model().objects.filter(user=user, application=application).delete()
    return OAuthConsent.objects.filter(user=user, application=application).delete()[0]


class ConnectedAppRevokeView(APIView):
    permission_classes = [IsAuthenticated]
    throttle_classes = [ScopedRateThrottle]
    throttle_scope = "oauth_consent"

    @extend_schema(tags=TAGS, summary="Disconnect an app (its tokens stop working at once)", request=None,
                   responses={204: None, **errors(401, 404, 429)})
    def delete(self, request, application_id):
        application = get_object_or_404(get_application_model(), pk=application_id)
        with transaction.atomic():
            if disconnect(request.user, application):
                audit.record(request.user, "oauth_consent.revoked", target=application,
                             makerspace=getattr(getattr(application, "spaceworks_registration", None), "makerspace", None))
        return Response(status=status.HTTP_204_NO_CONTENT)
