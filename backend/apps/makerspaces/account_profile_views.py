"""Account-level profile endpoints: the owner's read/write, the handle, and reads by account id.

Mounted under `/api/v1/member/profile/...` (owner) and `/api/v1/profiles/by-account/<id>/`
(signed-in readers). The owner is always `request.user` -- no route accepts a profile or user id
for a write, so there is nothing to forge. The old per-space routes subclass these in
`profile_legacy_aliases` and only add the membership check.
"""

from drf_spectacular.utils import OpenApiResponse, extend_schema
from rest_framework import serializers
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.accounts.account_kind_guards import require_member_account
from apps.accounts.authentication import SpaceWorksJWTAuthentication
from apps.hardware_requests.exceptions import ErrorSerializer

from . import account_profile
from .account_profile_access import resolve_by_account
from .account_profile_read import build_payload
from .account_profile_serializers import AccountProfileSerializer, AccountProfileWriteSerializer
from .public_profile_handles import claim_handle, release_handle
from .throttles import PROFILE_LOOKUP_THROTTLES

ERRORS = {
    401: OpenApiResponse(description="Authentication required."),
    403: OpenApiResponse(ErrorSerializer, description="A personal account is required."),
    404: OpenApiResponse(ErrorSerializer, description="Not found."),
}


class HandleSerializer(serializers.Serializer):
    handle = serializers.CharField(max_length=30)


class HandleReadSerializer(serializers.Serializer):
    handle = serializers.CharField()
    claimed_at = serializers.DateTimeField()
    changed_at = serializers.DateTimeField()


class AccountOwnerView(APIView):
    """Base: authenticated personal accounts only. `actor` is the single seam legacy routes widen."""

    permission_classes = [IsAuthenticated]
    audit_space = None

    def actor(self, request, **kwargs):
        require_member_account(request.user)
        return request.user

    def owner_payload(self, user):
        profile = account_profile.account_profile_for(user)
        return build_payload(profile, "owner")


class GlobalProfileView(AccountOwnerView):
    @extend_schema(tags=["Member profile"], summary="Retrieve the caller's own global profile",
                   request=None, responses={200: AccountProfileSerializer, **ERRORS})
    def get(self, request, **kwargs):
        user = self.actor(request, **kwargs)
        return Response(AccountProfileSerializer(self.owner_payload(user)).data)

    @extend_schema(tags=["Member profile"], summary="Update the caller's own global profile",
                   request=AccountProfileWriteSerializer,
                   responses={200: AccountProfileSerializer, 400: ErrorSerializer, **ERRORS})
    def put(self, request, **kwargs):
        user = self.actor(request, **kwargs)
        data = AccountProfileWriteSerializer(data=request.data)
        data.is_valid(raise_exception=True)
        account_profile.save_profile(user, data.validated_data, makerspace=self.audit_space)
        return Response(AccountProfileSerializer(self.owner_payload(user)).data)

    @extend_schema(tags=["Member profile"], request=AccountProfileWriteSerializer,
                   responses={200: AccountProfileSerializer, 400: ErrorSerializer, **ERRORS})
    def patch(self, request, **kwargs):
        return self.put(request, **kwargs)


class AccountHandleView(AccountOwnerView):
    @extend_schema(tags=["Member profile"], summary="Claim or change the profile handle",
                   request=HandleSerializer,
                   responses={200: HandleReadSerializer, 400: ErrorSerializer, **ERRORS})
    def post(self, request, **kwargs):
        user = self.actor(request, **kwargs)
        data = HandleSerializer(data=request.data)
        data.is_valid(raise_exception=True)
        account_profile.account_profile_for(user)
        return Response(HandleReadSerializer(claim_handle(user, data.validated_data["handle"])).data)

    @extend_schema(tags=["Member profile"], summary="Release the profile handle", request=None,
                   responses={204: None, **ERRORS})
    def delete(self, request, **kwargs):
        release_handle(self.actor(request, **kwargs))
        return Response(status=204)


class ProfileByAccountView(APIView):
    """Signed-in readers only: a member with no handle is reachable by account id (305c)."""

    authentication_classes = [SpaceWorksJWTAuthentication]
    permission_classes = [IsAuthenticated]
    throttle_classes = list(PROFILE_LOOKUP_THROTTLES)

    @extend_schema(tags=["Public profiles"], summary="Read a profile by account id (signed-in)",
                   request=None, responses={200: AccountProfileSerializer, **ERRORS,
                                            429: OpenApiResponse(description="Request rate exceeded.")})
    def get(self, request, user_id):
        profile = resolve_by_account(user_id, request.user, request)
        audience = "owner" if profile.user_id == request.user.pk else "member"
        return Response(AccountProfileSerializer(build_payload(profile, audience, request.user)).data)
