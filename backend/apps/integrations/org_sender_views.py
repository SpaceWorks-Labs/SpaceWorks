"""GET/PUT a co-hosting organisation's event-email sender (X2, #115a)."""

from drf_spectacular.utils import extend_schema
from rest_framework import serializers
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.admin_api.permissions import IsActiveStaff
from apps.organizations.access import require_governance
from apps.organizations.governance import MANAGE_ORGANIZATION_PROFILE
from apps.organizations.views_admin import ERRORS, WRITE_ERRORS, _organization

from .org_sender import update_sender


class OrganizationEmailSenderSerializer(serializers.Serializer):
    sender_name = serializers.CharField(max_length=80, allow_blank=True, help_text=(
        "Shown as '<name> via <space>' on event email from spaces that allow co-host senders."))
    reply_to = serializers.EmailField(max_length=254, allow_blank=True)
    updated_at = serializers.DateTimeField(read_only=True, allow_null=True)


def _payload(organization):
    from .models_org_sender import OrganizationEmailSender
    row = OrganizationEmailSender.objects.filter(organization=organization).first()
    return {"sender_name": row.sender_name if row else "", "reply_to": row.reply_to if row else "",
            "updated_at": row.updated_at if row else None}


class OrganizationEmailSenderView(APIView):
    permission_classes = [IsActiveStaff]

    @extend_schema(tags=["Organizations"], responses={200: OrganizationEmailSenderSerializer, **ERRORS},
                   description="Requires manage_organization_profile in this organization, or the superadmin.")
    def get(self, request, pk):
        organization = _organization(request.user, pk)
        require_governance(request.user, organization, MANAGE_ORGANIZATION_PROFILE)
        return Response(OrganizationEmailSenderSerializer(_payload(organization)).data)

    @extend_schema(tags=["Organizations"], request=OrganizationEmailSenderSerializer,
                   responses={200: OrganizationEmailSenderSerializer, **WRITE_ERRORS},
                   description="Set the display name and Reply-To used on event email when this organisation "
                               "co-hosts. The From address and mail provider stay the hosting space's. Audited "
                               "as organization.email_sender_updated.")
    def put(self, request, pk):
        organization = _organization(request.user, pk)
        payload = OrganizationEmailSenderSerializer(data=request.data)
        payload.is_valid(raise_exception=True)
        update_sender(organization, request.user, **payload.validated_data)
        return Response(OrganizationEmailSenderSerializer(_payload(organization)).data)
