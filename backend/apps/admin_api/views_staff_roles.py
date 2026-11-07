"""``makerspaces/<id>/staff-roles/``: staff roles on people (replaces staff-accounts, U-B).

Every route needs recent re-authentication (reads included) and is in
``mfa_grace.STRICT_ROUTES``: real two-step proof, even during a staff MFA grace.
The superadmin reaches the same routes for any space through Lane D's surface.
"""

from django.utils.translation import gettext
from drf_spectacular.utils import OpenApiParameter, extend_schema
from rest_framework.exceptions import ValidationError
from rest_framework.generics import GenericAPIView
from rest_framework.pagination import PageNumberPagination
from rest_framework.response import Response

from apps.accounts import staff_account_lifecycle as lifecycle, staff_account_services as service
from apps.accounts.reauthentication import require_recent_reauth
from apps.accounts.reauthentication_permissions import RecentReauthenticationMixin
from apps.accounts.services_staff_invitations import issue, onboarding_available
from apps.accounts.staff_account_policy import scoped_space
from apps.accounts.staff_invitation_delivery import deliver
from apps.admin_api.permissions import IsActiveStaff
from apps.admin_api.serializers_staff_roles import (
    StaffRoleChangeSerializer, StaffRoleCreateSerializer, StaffRoleCreatedSerializer, StaffRoleListSerializer,
    StaffRoleRevokeSerializer, StaffRoleSerializer,
)
from apps.hardware_requests.exceptions import ErrorSerializer
from apps.makerspaces.models import MakerspaceMembership
from apps.makerspaces.role_catalog import ROLE_BY_SLUG

ERRORS = {code: ErrorSerializer for code in (400, 401, 403, 404, 409, 423, 429, 503)}
TAGS = ["Staff roles"]


def _no_store(response):
    response["Cache-Control"] = "private, no-store"
    return response


class StaffRoleBase(RecentReauthenticationMixin, GenericAPIView):
    permission_classes = [IsActiveStaff]
    serializer_class = StaffRoleSerializer
    pagination_class = PageNumberPagination

    def initial(self, request, *args, **kwargs):
        super().initial(request, *args, **kwargs)
        if request.method in {"GET", "HEAD"}:
            require_recent_reauth(request)

    def context_for(self, request, makerspace_id):
        space, actor = scoped_space(request.user, makerspace_id)
        return {"space": space, "actor": actor, "request": request}

    def row_response(self, request, makerspace_id, row, status=200):
        return _no_store(Response(StaffRoleSerializer(row, context=self.context_for(request, makerspace_id)).data,
                                  status=status))


def policy(space, superadmin):
    from apps.machines.member_scope_services import assignable_machine_types

    names = dict(space.roles.values_list("slug", "name"))
    grantable = [{"slug": slug, "name": names[slug], "combinable": entry.combinable}
                 for slug, entry in ROLE_BY_SLUG.items()
                 if slug != "member" and slug in names and (slug != "space_manager" or superadmin)]
    return {"grantable_roles": grantable, "can_manage_space_managers": superadmin,
            "email_invites_available": onboarding_available(space),
            "machine_types": list(assignable_machine_types(space).values("id", "name"))}


class StaffRoleListCreateView(StaffRoleBase):
    @extend_schema(tags=TAGS, summary="List a makerspace's staff roles",
                   description="One row per person holding staff roles here, with the viewer's policy "
                               "(grantable roles, machine types, whether email invitations are on).",
                   parameters=[OpenApiParameter("include_revoked", str, enum=["0", "1"])],
                   responses={200: StaffRoleListSerializer, **ERRORS})
    def get(self, request, makerspace_id):
        from apps.accounts.platform_authority import is_platform_superadmin

        context = self.context_for(request, makerspace_id)
        include = request.query_params.get("include_revoked", "0")
        if include not in {"0", "1"}:
            raise ValidationError({"include_revoked": gettext("Use 0 or 1.")})
        rows = MakerspaceMembership.staff_tracks.filter(makerspace=context["space"]).select_related("user")
        if include != "1":
            rows = rows.filter(status="active")
        page = self.paginate_queryset(rows.order_by("user__username", "pk"))
        response = self.get_paginated_response(StaffRoleSerializer(page, many=True, context=context).data)
        response.data["policy"] = policy(context["space"], is_platform_superadmin(context["actor"]))
        return _no_store(response)

    @extend_schema(tags=TAGS, summary="Grant a staff role, or invite by email",
                   description="`user_id` grants to an active community member of this space "
                               "(`not_community_member` otherwise). `email` always sends an invitation that "
                               "the invitee accepts while signed in; the link goes to them only. Only the "
                               "superadmin grants the Space Manager role (`space_manager_superadmin_only`).",
                   request=StaffRoleCreateSerializer, responses={201: StaffRoleCreatedSerializer, **ERRORS})
    def post(self, request, makerspace_id):
        data = StaffRoleCreateSerializer(data=request.data)
        data.is_valid(raise_exception=True)
        values = data.validated_data
        if values.get("user_id"):
            row = service.grant(request.user, makerspace_id, user_id=values["user_id"], roles=values["roles"],
                                machine_type_ids=values["machine_type_ids"])
            staff_role = StaffRoleSerializer(row, context=self.context_for(request, makerspace_id)).data
            body = {"kind": "granted", "staff_role": staff_role, "invitation_id": None, "delivery_status": None}
        else:
            invitation, raw = issue(request.user, makerspace_id, email=values["email"], roles=values["roles"],
                                    machine_type_ids=values["machine_type_ids"],
                                    expires_in_days=values["expires_in_days"])
            body = {"kind": "invited", "staff_role": None, "invitation_id": invitation.pk,
                    "delivery_status": deliver(invitation, raw)["delivery_status"]}
        return _no_store(Response(body, status=201))


class StaffRoleDetailView(StaffRoleBase):
    @extend_schema(tags=TAGS, summary="Change a staff row's roles or machine scopes",
                   request=StaffRoleChangeSerializer, responses={200: StaffRoleSerializer, **ERRORS})
    def patch(self, request, makerspace_id, membership_id):
        data = StaffRoleChangeSerializer(data=request.data)
        data.is_valid(raise_exception=True)
        row = service.change(request.user, makerspace_id, membership_id, **data.validated_data)
        return self.row_response(request, makerspace_id, row)


class StaffRoleRevokeView(StaffRoleBase):
    @extend_schema(tags=TAGS, summary="Revoke a staff row",
                   description="Ends this staff authority only; the person's member features keep working "
                               "and their staff device grants here are revoked. `last_manager` refuses the "
                               "space's last Space Manager.",
                   request=StaffRoleRevokeSerializer, responses={200: StaffRoleSerializer, **ERRORS})
    def post(self, request, makerspace_id, membership_id):
        data = StaffRoleRevokeSerializer(data=request.data)
        data.is_valid(raise_exception=True)
        row = lifecycle.revoke(request.user, makerspace_id, membership_id, **data.validated_data)
        return self.row_response(request, makerspace_id, row)


class StaffRoleRestoreView(StaffRoleBase):
    @extend_schema(tags=TAGS, summary="Restore a revoked staff row", request=None,
                   responses={200: StaffRoleSerializer, **ERRORS})
    def post(self, request, makerspace_id, membership_id):
        row = lifecycle.restore(request.user, makerspace_id, membership_id)
        return self.row_response(request, makerspace_id, row)
