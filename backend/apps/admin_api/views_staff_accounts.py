"""Tenant staff lifecycle endpoints; all mutations share browser step-up."""

from drf_spectacular.utils import OpenApiParameter, extend_schema
from rest_framework.generics import GenericAPIView
from rest_framework.pagination import PageNumberPagination
from rest_framework.response import Response
from rest_framework.exceptions import ValidationError

from apps.accounts import rbac, staff_account_lifecycle as lifecycle, staff_account_services as service
from apps.accounts.models import User
from apps.accounts.reauthentication_permissions import RecentReauthenticationMixin
from apps.accounts.reauthentication import require_recent_reauth
from apps.accounts.services_staff_invitations import onboarding_available, resend_account
from apps.accounts.staff_account_policy import require_authority, scoped_space
from apps.accounts.staff_invitation_delivery import deliver
from apps.admin_api.permissions import IsActiveStaff
from apps.admin_api.serializers_staff_accounts import (
    StaffAccountChangeSerializer, StaffAccountCreateSerializer, StaffAccountCreatedSerializer,
    StaffAccountDeactivateSerializer, StaffAccountInvitationResultSerializer,
    StaffAccountPasswordResultSerializer, StaffAccountPasswordSerializer,
    StaffAccountPolicySerializer, StaffAccountSerializer,
)
from apps.makerspaces.role_catalog import BUILTIN_ROLE_SLUGS
from apps.machines.member_scope_services import assignable_machine_types
from apps.admin_api.serializers_roles import RoleSerializer, role_queryset
from apps.hardware_requests.exceptions import ErrorSerializer

ERRORS = {code: ErrorSerializer for code in (400, 401, 403, 404, 409, 423, 429, 503)}


def invitation_sent(invitation):
    if invitation is None:
        return False
    row, raw = invitation
    return deliver(row, raw)["delivery_status"] == "sent"


class StaffAccountBase(RecentReauthenticationMixin, GenericAPIView):
    permission_classes = [IsActiveStaff]
    serializer_class = StaffAccountSerializer
    pagination_class = PageNumberPagination

    def initial(self, request, *args, **kwargs):
        super().initial(request, *args, **kwargs)
        if request.method in {"GET", "HEAD"}:
            require_recent_reauth(request)

    def context_for(self, request, makerspace_id):
        space, actor = scoped_space(request.user, makerspace_id)
        return {"space": space, "actor": actor, "request": request}

    def account_response(self, request, makerspace_id, account):
        response = Response(StaffAccountSerializer(account,
            context=self.context_for(request, makerspace_id)).data)
        response["Cache-Control"] = "private, no-store"
        return response


class StaffAccountListCreateView(StaffAccountBase):
    @extend_schema(tags=["Staff accounts"], parameters=[OpenApiParameter("include_inactive", str, enum=["0", "1"])],
                   responses={200: StaffAccountSerializer(many=True), **ERRORS})
    def get(self, request, makerspace_id):
        context = self.context_for(request, makerspace_id)
        rows = rbac.scope_by_makerspace(request.user, User.objects.filter(account_kind="staff",
            retired_at__isnull=True, staff_makerspace=context["space"]), "staff_makerspace_id")
        include_inactive = request.query_params.get("include_inactive", "0")
        if include_inactive not in {"0", "1"}:
            raise ValidationError({"include_inactive": "Use 0 or 1."})
        if include_inactive != "1":
            rows = rows.filter(is_active=True)
        page = self.paginate_queryset(rows.order_by("username", "pk"))
        response = self.get_paginated_response(StaffAccountSerializer(page, many=True, context=context).data)
        response["Cache-Control"] = "private, no-store"
        return response

    @extend_schema(tags=["Staff accounts"], request=StaffAccountCreateSerializer,
                   responses={201: StaffAccountCreatedSerializer, **ERRORS})
    def post(self, request, makerspace_id):
        data = StaffAccountCreateSerializer(data=request.data)
        data.is_valid(raise_exception=True)
        account, invitation = service.create(request.user, makerspace_id, **data.validated_data)
        response = Response({"account": StaffAccountSerializer(account,
            context=self.context_for(request, makerspace_id)).data,
            "invitation_sent": invitation_sent(invitation)}, status=201)
        response["Cache-Control"] = "private, no-store"
        return response


class StaffAccountPolicyView(StaffAccountBase):
    @extend_schema(tags=["Staff accounts"], responses={200: StaffAccountPolicySerializer, **ERRORS})
    def get(self, request, makerspace_id):
        context = self.context_for(request, makerspace_id)
        space, actor = context["space"], context["actor"]
        managers = require_authority(actor, space)
        response = Response({"creatable_roles": [key for key in BUILTIN_ROLE_SLUGS
            if key != "member" and (key != "space_manager" or managers)],
            "can_manage_space_managers": managers,
            "machine_types": list(assignable_machine_types(space).values("id", "name")),
            "roles": RoleSerializer(role_queryset().filter(makerspace=space), many=True).data,
            "email_onboarding_available": onboarding_available(space)})
        response["Cache-Control"] = "private, no-store"
        return response


class StaffAccountChangeView(StaffAccountBase):
    @extend_schema(tags=["Staff accounts"], request=StaffAccountChangeSerializer,
                   responses={200: StaffAccountSerializer, **ERRORS})
    def patch(self, request, makerspace_id, user_id):
        data = StaffAccountChangeSerializer(data=request.data)
        data.is_valid(raise_exception=True)
        account = service.change(request.user, makerspace_id, user_id, **data.validated_data)
        return self.account_response(request, makerspace_id, account)


class StaffAccountDeactivateView(StaffAccountBase):
    @extend_schema(tags=["Staff accounts"], request=StaffAccountDeactivateSerializer,
                   responses={200: StaffAccountSerializer, **ERRORS})
    def post(self, request, makerspace_id, user_id):
        data = StaffAccountDeactivateSerializer(data=request.data)
        data.is_valid(raise_exception=True)
        account = lifecycle.deactivate(request.user, makerspace_id, user_id, **data.validated_data)
        return self.account_response(request, makerspace_id, account)


class StaffAccountReactivateView(StaffAccountBase):
    @extend_schema(tags=["Staff accounts"], request=None, responses={200: StaffAccountSerializer, **ERRORS})
    def post(self, request, makerspace_id, user_id):
        return self.account_response(request, makerspace_id,
            lifecycle.reactivate(request.user, makerspace_id, user_id))


class StaffAccountSetPasswordView(StaffAccountBase):
    @extend_schema(tags=["Staff accounts"], request=StaffAccountPasswordSerializer,
                   responses={200: StaffAccountPasswordResultSerializer, **ERRORS})
    def post(self, request, makerspace_id, user_id):
        data = StaffAccountPasswordSerializer(data=request.data)
        data.is_valid(raise_exception=True)
        response = Response(lifecycle.set_password(request.user, makerspace_id, user_id, **data.validated_data))
        response["Cache-Control"] = "private, no-store"
        return response


class StaffAccountResendInviteView(StaffAccountBase):
    @extend_schema(tags=["Staff accounts"], request=None,
                   responses={200: StaffAccountInvitationResultSerializer, **ERRORS})
    def post(self, request, makerspace_id, user_id):
        response = Response({"invitation_sent": invitation_sent(resend_account(request.user, makerspace_id, user_id))})
        response["Cache-Control"] = "private, no-store"
        return response
