"""Account-merge endpoints: a person links a former staff account into the signed-in one.

Member-only routes (``ACCOUNT_MERGE_ROUTES``), never reachable from a claim session.
``start`` sits behind the login IP guard (``login_ip_guard``; S-C) and per-person
throttles; proofs and confirm have their own budget. Confirm also needs recent
re-authentication, and staff MFA when the person already holds elevated authority.
"""

from django.db import transaction
from drf_spectacular.utils import OpenApiResponse, extend_schema
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.throttling import SimpleRateThrottle
from rest_framework.views import APIView

from apps.accounts import account_merge, account_merge_proofs as proofs
from apps.accounts.account_merge_eligibility import PROOF_EXPIRED, MergeRefused, require_survivor
from apps.accounts.serializers_account_merge import (
    MergeConfirmRequestSerializer, MergeConfirmResponseSerializer, MergeErrorSerializer, MergeIntentSerializer,
    MergePreviewSerializer, MergeProveRequestSerializer, MergeStartRequestSerializer,
)
from apps.openapi_errors import errors

_REFUSED = OpenApiResponse(MergeErrorSerializer, description="Typed refusal: see `code`.")


class _PersonThrottle(SimpleRateThrottle):
    def get_cache_key(self, request, view):
        return self.cache_format % {"scope": self.scope, "ident": request.user.pk}


class AccountMergeStartThrottle(_PersonThrottle):
    scope = "account_merge_start"


class AccountMergeProveThrottle(_PersonThrottle):
    scope = "account_merge_prove"


def _no_store(data, status=200):
    response = Response(data, status=status)
    response["Cache-Control"] = "private, no-store"
    return response


class _MergeView(APIView):
    permission_classes = [IsAuthenticated]
    throttle_classes = [AccountMergeProveThrottle]


class AccountMergeStartView(_MergeView):
    throttle_classes = [AccountMergeStartThrottle]
    login_ip_guard = True  # S-C's login IP guard; a no-op until it lands.

    @extend_schema(tags=["Accounts"], request=MergeStartRequestSerializer,
                   responses={201: MergeIntentSerializer, 403: _REFUSED, **errors(400, 401, 429)},
                   description="Start linking another account into this one. The answer is the same whether or "
                               "not the identifier names an account. `email_codes` sends one code to this "
                               "account's email and one to the other account's email (two codes even when it is "
                               "the same mailbox); `credentials` sends nothing.")
    def post(self, request):
        data = MergeStartRequestSerializer(data=request.data)
        data.is_valid(raise_exception=True)
        intent = proofs.start(request.user, data.validated_data["identifier"], data.validated_data["method"])
        return _no_store(MergeIntentSerializer(intent).data, status=201)


class AccountMergeProveView(_MergeView):
    @extend_schema(tags=["Accounts"], request=MergeProveRequestSerializer,
                   responses={200: MergeIntentSerializer, 400: _REFUSED, 409: _REFUSED, 410: _REFUSED,
                              **errors(401, 404, 429)},
                   description="Prove the other account: its password and authenticator code (`credentials`), or "
                               "both emailed codes (`email_codes`). Codes work once; five wrong tries end the request.")
    def post(self, request, intent_id):
        data = MergeProveRequestSerializer(data=request.data)
        data.is_valid(raise_exception=True)
        intent = proofs.prove(request.user, intent_id, data.validated_data)
        return _no_store(MergeIntentSerializer(intent).data)


class AccountMergeResendView(_MergeView):
    throttle_classes = [AccountMergeStartThrottle]

    @extend_schema(tags=["Accounts"], request=None,
                   responses={200: MergeIntentSerializer, 410: _REFUSED, **errors(401, 404, 429)},
                   description="Send two new codes (email_codes only); the old codes stop working.")
    def post(self, request, intent_id):
        return _no_store(MergeIntentSerializer(proofs.resend(request.user, intent_id)).data)


class AccountMergePreviewView(_MergeView):
    @extend_schema(tags=["Accounts"], responses={200: MergePreviewSerializer, 403: _REFUSED, 410: _REFUSED,
                                                 **errors(401, 404, 429)},
                   description="What linking will do: staff roles gained per makerspace, records that move or stay, "
                               "one-per-person conflicts and whether the staff two-step grace opens.")
    def get(self, request, intent_id):
        from apps.accounts.account_merge_preview import build
        from apps.accounts.models_account_merge import AccountMergeIntent as Intent
        from django.utils import timezone

        require_survivor(request.user)
        with transaction.atomic():
            intent = proofs.locked_intent(request.user, intent_id)
            if intent.state != Intent.State.PROVED or timezone.now() >= intent.expires_at or intent.source is None:
                raise MergeRefused(PROOF_EXPIRED, "Prove the other account again.")
            body = build(request.user, intent.source)
            intent.preview_sha256 = body["preview_sha256"]
            intent.save(update_fields=["preview_sha256"])
        return _no_store({**body, "expires_at": intent.expires_at})


class AccountMergeConfirmView(_MergeView):
    @extend_schema(tags=["Accounts"], request=MergeConfirmRequestSerializer,
                   responses={200: MergeConfirmResponseSerializer, 403: _REFUSED, 409: _REFUSED, 410: _REFUSED,
                              **errors(401, 404, 429)},
                   description="Link the proved account into this one, exactly as previewed. Needs re-authentication "
                               "within ten minutes (`recent_reauth_required`). Cannot be undone.")
    def post(self, request, intent_id):
        data = MergeConfirmRequestSerializer(data=request.data)
        data.is_valid(raise_exception=True)
        result = account_merge.confirm(request, intent_id, data.validated_data["preview_sha256"])
        return _no_store(MergeConfirmResponseSerializer(result).data)


class AccountMergeCancelView(_MergeView):
    @extend_schema(tags=["Accounts"], request=None, responses={200: MergeIntentSerializer, **errors(401, 404, 429)},
                   description="Abandon a link request; its codes stop working.")
    def post(self, request, intent_id):
        return _no_store(MergeIntentSerializer(proofs.cancel(request.user, intent_id)).data)
