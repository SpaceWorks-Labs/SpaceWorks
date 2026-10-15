from drf_spectacular.utils import extend_schema
from rest_framework import serializers
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.accounts.reauthentication import require_recent_reauth
from apps.admin_api.permissions import IsActiveStaff
from apps.organizations.models import OrganizationMembership
from apps.organizations.serializers_admin import OrganizationMembershipSerializer
from apps.organizations.services_governance import update_membership
from apps.organizations.views_admin import _organization
from apps.organizations.views_console import console_errors


class OrganizationMembershipUpdateSerializer(serializers.Serializer):
    status = serializers.ChoiceField(choices=OrganizationMembership.Status.choices, required=False)
    governance_actions = serializers.ListField(child=serializers.CharField(), required=False)
    granted_actions = serializers.ListField(child=serializers.CharField(), required=False)


class OrganizationMembershipDetailView(APIView):
    permission_classes = [IsActiveStaff]

    @extend_schema(tags=["Admin organizations"], request=OrganizationMembershipUpdateSerializer,
                   responses={200: OrganizationMembershipSerializer,
                              **console_errors(400, 401, 403, 404, 409)})
    def patch(self, request, pk, membership_id):
        organization = _organization(request.user, pk)
        require_recent_reauth(request)
        payload = OrganizationMembershipUpdateSerializer(data=request.data)
        payload.is_valid(raise_exception=True)
        row = update_membership(organization, membership_id, actor=request.user,
                                **payload.validated_data)
        return Response(OrganizationMembershipSerializer(row).data)
