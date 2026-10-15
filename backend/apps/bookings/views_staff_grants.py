from django.shortcuts import get_object_or_404
from drf_spectacular.utils import OpenApiResponse, extend_schema
from rest_framework.exceptions import PermissionDenied
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.throttling import SimpleRateThrottle
from rest_framework.views import APIView

from apps.admin_api.permissions import IsActiveStaff, active_user
from apps.hardware_requests.exceptions import ErrorSerializer
from apps.makerspaces.origin_scope import (
    AMBIGUOUS_STAFF_ORIGIN_SCOPE, NO_STAFF_ORIGIN_SCOPE, staff_origin_scope,
)

from . import booking_authority, services_staff_grants as services
from .models_staff_grants import BookingSpaceStaffGrant, BookingSpaceStaffGrantInvite
from .serializers_admin import EmptyActionSerializer
from .serializers_staff_grants import (
    BookingStaffGrantInviteCreatedSerializer, BookingStaffGrantInviteInputSerializer,
    BookingStaffGrantInviteListSerializer, BookingStaffGrantInviteSerializer,
    BookingStaffGrantListSerializer, BookingStaffGrantPermissionsSerializer,
    BookingStaffGrantRedeemSerializer, BookingStaffGrantSerializer,
)
from .views_grant_pagination import PAGE_PARAMETERS, paginated

ERRORS = {code: ErrorSerializer for code in (401, 403, 404, 409, 423, 429, 503)}
ERRORS[400] = OpenApiResponse({"type": "object", "additionalProperties": {}},
                            description="Field validation, module or feature disabled.")
MANAGER_CONTRACT = ("Requires live tenant MANAGE_BOOKINGS and bookings.staff_grants. "
                    "Resource grantees cannot delegate. Invitations expire after seven days; "
                    "sender authority and permission subset are rechecked on redemption.")


class StaffGrantRedeemThrottle(SimpleRateThrottle):
    scope = "booking_staff_grant_redeem"
    rate = "10/min"

    def get_cache_key(self, request, view):
        return self.cache_format % {"scope": self.scope, "ident": request.user.pk}


class BookingStaffGrantListView(APIView):
    permission_classes = [IsActiveStaff]

    def target(self, request, pk):
        target = booking_authority.get_space(request.user, pk, None)
        services.require_feature(target)
        return target

    def rows(self, model, target):
        return model.objects.filter(space=target, makerspace_id=target.makerspace_id).order_by("id")

    @extend_schema(tags=["Admin bookings"], description=MANAGER_CONTRACT, request=None, parameters=PAGE_PARAMETERS,
                   responses={200: BookingStaffGrantListSerializer, **ERRORS})
    def get(self, request, pk):
        return paginated(request, self.rows(BookingSpaceStaffGrant, self.target(request, pk)), BookingStaffGrantSerializer)


class BookingStaffInviteListView(BookingStaffGrantListView):
    @extend_schema(tags=["Admin bookings"], description=MANAGER_CONTRACT, request=None, parameters=PAGE_PARAMETERS,
                   responses={200: BookingStaffGrantInviteListSerializer, **ERRORS})
    def get(self, request, pk):
        return paginated(request, self.rows(BookingSpaceStaffGrantInvite, self.target(request, pk)), BookingStaffGrantInviteSerializer)

    @extend_schema(tags=["Admin bookings"], description=MANAGER_CONTRACT, request=BookingStaffGrantInviteInputSerializer,
                   responses={201: BookingStaffGrantInviteCreatedSerializer, **ERRORS})
    def post(self, request, pk):
        target = self.target(request, pk)
        serializer = BookingStaffGrantInviteInputSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        row, token = services.create_invite(target, actor=request.user, **serializer.validated_data)
        response = Response({**BookingStaffGrantInviteSerializer(row).data, "token": token}, status=201)
        response["Cache-Control"] = "private, no-store"
        return response


def _manageable_row(actor, model, pk):
    row = get_object_or_404(model.objects.select_related("space__makerspace").filter(
        space_id__in=booking_authority.visible_spaces(actor).values("pk")), pk=pk)
    booking_authority.require(actor, row.space, None)
    services.require_feature(row.space)
    return row


class BookingStaffGrantDetailView(APIView):
    permission_classes = [IsActiveStaff]

    @extend_schema(tags=["Admin bookings"], description=MANAGER_CONTRACT, request=BookingStaffGrantPermissionsSerializer,
                   responses={200: BookingStaffGrantSerializer, **ERRORS})
    def patch(self, request, pk):
        row = _manageable_row(request.user, BookingSpaceStaffGrant, pk)
        serializer = BookingStaffGrantPermissionsSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        return Response(BookingStaffGrantSerializer(services.update_permissions(
            row, actor=request.user, **serializer.validated_data,
        )).data)


class BookingStaffGrantRevokeView(APIView):
    permission_classes = [IsActiveStaff]

    @extend_schema(tags=["Admin bookings"], description=MANAGER_CONTRACT, request=EmptyActionSerializer,
                   responses={200: BookingStaffGrantSerializer, **ERRORS})
    def post(self, request, pk):
        row = _manageable_row(request.user, BookingSpaceStaffGrant, pk)
        EmptyActionSerializer(data=request.data).is_valid(raise_exception=True)
        return Response(BookingStaffGrantSerializer(services.revoke_grant(row, actor=request.user)).data)


class BookingStaffInviteRevokeView(APIView):
    permission_classes = [IsActiveStaff]

    @extend_schema(tags=["Admin bookings"], description=MANAGER_CONTRACT, request=EmptyActionSerializer,
                   responses={200: BookingStaffGrantInviteSerializer, **ERRORS})
    def post(self, request, pk):
        row = _manageable_row(request.user, BookingSpaceStaffGrantInvite, pk)
        EmptyActionSerializer(data=request.data).is_valid(raise_exception=True)
        return Response(BookingStaffGrantInviteSerializer(services.revoke_invite(row, actor=request.user)).data)


class BookingStaffInviteRedeemView(APIView):
    permission_classes = [IsAuthenticated]
    throttle_classes = [StaffGrantRedeemThrottle]

    @extend_schema(tags=["Bookings"], description="Authenticated active account; single-use invite with verified email binding, current sender authority, selected tenant/origin, expiry and revocation checks. Rate limited to 10/min/account; private/no-store.", request=BookingStaffGrantRedeemSerializer,
                   responses={200: BookingStaffGrantSerializer, **ERRORS})
    def post(self, request):
        if not active_user(request.user):
            raise PermissionDenied()
        scope = staff_origin_scope(request)
        if scope is AMBIGUOUS_STAFF_ORIGIN_SCOPE:
            raise PermissionDenied()
        serializer = BookingStaffGrantRedeemSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        grant = services.redeem_invite(
            serializer.validated_data["token"], actor=request.user,
            makerspace_id=None if scope is NO_STAFF_ORIGIN_SCOPE else scope,
        )
        response = Response(BookingStaffGrantSerializer(grant).data)
        response["Cache-Control"] = "private, no-store"
        return response
