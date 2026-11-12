"""Passkey endpoints for a browser or (358 B) a phone session. Errors: ``passkey_failed``,
``passkeys_unavailable``, ``rp_id_unavailable``, ``last_factor``, ``recent_reauth_required``.
Native passwordless sign-in is under ``auth/device/passkey/*`` (`native_login.py`)."""

import json

from drf_spectacular.utils import extend_schema
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.throttling import ScopedRateThrottle
from rest_framework.views import APIView

from apps.accounts.auth_cookies import set_refresh_cookies
from apps.accounts.models_webauthn import WebAuthnCredential
from apps.accounts.passkeys import assertion, services
from apps.accounts.passkeys.policy import passkeys_usable
from apps.accounts.passkeys.native import assert_person_session, ceremony_scope
from apps.accounts.passkeys.rp_id import RpIdUnavailable
from apps.accounts.passkeys.serializers import (
    PasskeyListSerializer, PasskeyLoginSerializer, PasskeyMfaOptionsRequestSerializer,
    PasskeyOptionsSerializer, PasskeyReauthenticatedSerializer, PasskeyRegisteredSerializer,
    PasskeyRegisterRequestSerializer, PasskeyRemovedSerializer, PasskeyRenameSerializer, PasskeySerializer,
    PasskeyVerifyRequestSerializer,
)
from apps.openapi_errors import errors

TAGS = ["Passkeys"]


def _data(cls, request):
    serializer = cls(data=request.data)
    serializer.is_valid(raise_exception=True)
    return serializer.validated_data


def _private(data, status=200):
    response = Response(data, status=status)
    response["Cache-Control"] = "no-store"
    return response


def _options(result):
    ceremony, options_json = result
    return _private({"ceremony": str(ceremony.pk), "options": json.loads(options_json)})


def _with_session(request, payload, session):
    if getattr(request, "device_grant", None) is not None:
        return _private({**payload, **session})  # a phone gets its new refresh token in the body
    raw = session.pop("refresh")
    response = _private({**payload, **session})
    set_refresh_cookies(response, raw, request)
    return response


def _rp_id(request):
    try:
        return ceremony_scope(request)[1]
    except RpIdUnavailable:
        return None


class _OptionsThrottled(APIView):
    throttle_classes = [ScopedRateThrottle]
    throttle_scope = "passkey_options"


class _VerifyThrottled(APIView):
    throttle_classes = [ScopedRateThrottle]
    throttle_scope = "passkey_verify"


class PasskeyListView(APIView):
    permission_classes = [IsAuthenticated]

    @extend_schema(tags=TAGS, summary="List my passkeys", responses={200: PasskeyListSerializer, **errors(401, 403)})
    def get(self, request):
        user = assert_person_session(request)
        rp_id = _rp_id(request)
        rows = WebAuthnCredential.objects.filter(user=user).order_by("created_at", "pk")
        return _private({"passkeys": PasskeySerializer(rows, many=True, context={"rp_id": rp_id}).data,
                         "passkeys_allowed": passkeys_usable(user), "rp_id": rp_id})


class PasskeyDetailView(APIView):
    permission_classes = [IsAuthenticated]

    @extend_schema(tags=TAGS, summary="Rename a passkey (recent re-authentication)", request=PasskeyRenameSerializer,
                   responses={200: PasskeySerializer, **errors(400, 401, 403, 404)})
    def patch(self, request, passkey_id):
        row = services.rename(request, passkey_id, _data(PasskeyRenameSerializer, request)["name"])
        return _private(PasskeySerializer(row, context={"rp_id": _rp_id(request)}).data)

    @extend_schema(tags=TAGS, summary="Remove a passkey (recent re-authentication)",
                   description="Ends every session. The calling browser gets a new one unless the removed "
                               "factor was its only proof. Refuses last_factor for staff.",
                   responses={200: PasskeyRemovedSerializer, **errors(400, 401, 403, 404)})
    def delete(self, request, passkey_id):
        session = services.remove(request, passkey_id)
        if session is None:
            return _private({"signed_out": True})
        return _with_session(request, {"signed_out": False}, session)


class PasskeyRegisterOptionsView(_OptionsThrottled):
    permission_classes = [IsAuthenticated]

    @extend_schema(tags=TAGS, summary="Start adding a passkey (recent re-authentication)", request=None,
                   responses={200: PasskeyOptionsSerializer, **errors(400, 401, 403, 429)})
    def post(self, request):
        return _options(services.begin_registration(request))


class PasskeyRegisterVerifyView(_VerifyThrottled):
    permission_classes = [IsAuthenticated]

    @extend_schema(tags=TAGS, summary="Finish adding a passkey", request=PasskeyRegisterRequestSerializer,
                   description="Ends every other session and returns a fresh one proved by the new passkey.",
                   responses={200: PasskeyRegisteredSerializer, **errors(400, 401, 403, 429)})
    def post(self, request):
        data = _data(PasskeyRegisterRequestSerializer, request)
        row, codes, session = services.finish_registration(request, data["ceremony"], data["credential"],
                                                           data.get("name", ""))
        passkey = PasskeySerializer(row, context={"rp_id": row.rp_id}).data
        return _with_session(request, {"passkey": passkey, "recovery_codes": codes}, session)


class PasskeyAuthenticateOptionsView(_OptionsThrottled):
    permission_classes = [AllowAny]

    @extend_schema(tags=TAGS, summary="Start a passkey sign-in (discoverable, conditional UI)", auth=[],
                   request=None, responses={200: PasskeyOptionsSerializer, **errors(400, 403, 429)})
    def post(self, request):
        return _options(assertion.begin_login(request))


class PasskeyAuthenticateVerifyView(_VerifyThrottled):
    permission_classes = [AllowAny]

    @extend_schema(tags=TAGS, summary="Sign in with a passkey", auth=[], request=PasskeyVerifyRequestSerializer,
                   responses={200: PasskeyLoginSerializer, **errors(400, 403, 429)})
    def post(self, request):
        data = _data(PasskeyVerifyRequestSerializer, request)
        return _with_session(request, {}, assertion.finish_login(request, data["ceremony"], data["credential"]))


class PasskeyMfaOptionsView(_OptionsThrottled):
    permission_classes = [AllowAny]

    @extend_schema(tags=TAGS, summary="Passkey options for a pending second-factor challenge", auth=[],
                   description="Answer with mfa/verify (factor=passkey). The challenge is not consumed here.",
                   request=PasskeyMfaOptionsRequestSerializer,
                   responses={200: PasskeyOptionsSerializer, **errors(400, 403, 429)})
    def post(self, request):
        return _options(assertion.begin_mfa(request, _data(PasskeyMfaOptionsRequestSerializer, request)["challenge"]))


class PasskeyReauthOptionsView(_OptionsThrottled):
    permission_classes = [IsAuthenticated]

    @extend_schema(tags=["Reauthentication"], summary="Start a passkey re-authentication", request=None,
                   responses={200: PasskeyOptionsSerializer, **errors(400, 401, 403, 429)})
    def post(self, request):
        return _options(assertion.begin_reauth(request))


class PasskeyReauthVerifyView(_VerifyThrottled):
    permission_classes = [IsAuthenticated]

    @extend_schema(tags=["Reauthentication"], summary="Re-authenticate with a passkey",
                   request=PasskeyVerifyRequestSerializer,
                   responses={200: PasskeyReauthenticatedSerializer, **errors(400, 401, 403, 429)})
    def post(self, request):
        data = _data(PasskeyVerifyRequestSerializer, request)
        return _private(assertion.finish_reauth(request, data["ceremony"], data["credential"]))
