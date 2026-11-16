"""Authenticated member-surface account departure with explicit confirmation."""

from drf_spectacular.utils import PolymorphicProxySerializer, extend_schema
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.accounts import account_deletion
from apps.accounts.auth_cookies import clear_refresh_cookies
from apps.accounts.serializers_account_deletion import (
    AccountDeletionPreviewSerializer, AccountDeletionRequestSerializer,
    AccountDeletionResultSerializer, AccountDeletionRefusedSerializer,
)
from apps.accounts.views_reauthentication import ReauthenticationThrottle
from apps.hardware_requests.exceptions import ErrorSerializer
from apps.openapi_errors import errors


def _response(data, *, status=200):
    result = Response(data, status=status)
    result["Cache-Control"] = "private, no-store"
    return result


class AccountDeletionView(APIView):
    permission_classes = [IsAuthenticated]
    throttle_classes = [ReauthenticationThrottle]

    @extend_schema(tags=["Accounts"], responses={200: AccountDeletionPreviewSerializer,
                                               **errors(401, 403, 429, 503)},
                   description="Preview global obligations and available fresh identity verification methods.")
    def get(self, request):
        return _response(account_deletion.preview(request))

    @extend_schema(tags=["Accounts"], request=AccountDeletionRequestSerializer,
                   responses={202: AccountDeletionResultSerializer, 409: AccountDeletionRefusedSerializer,
                              **errors(400, 401, 429, 503),
                              403: PolymorphicProxySerializer(component_name="AccountDeletionForbidden",
                                  serializers=[ErrorSerializer, AccountDeletionRefusedSerializer],
                                  resource_type_field_name=None)},
                   description="Requires session-bound reauthentication within ten minutes. Atomically archives "
                               "the account and revokes its credentials; retained records follow their retention policies.")
    def post(self, request):
        data = AccountDeletionRequestSerializer(data=request.data)
        data.is_valid(raise_exception=True)
        result = account_deletion.request_deletion(request)
        response = _response(AccountDeletionResultSerializer(result).data, status=202)
        clear_refresh_cookies(response)
        return response
