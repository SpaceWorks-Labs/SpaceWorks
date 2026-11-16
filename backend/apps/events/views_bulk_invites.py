from drf_spectacular.utils import extend_schema
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.admin_api.permissions import IsActiveStaff
from . import event_authority
from .event_permissions import MANAGE_INVITATIONS
from .serializers_broadcasts import BulkInviteInputSerializer, BulkInviteResultSerializer
from .services_bulk_invites import bulk_invites
from .views_invites import ERRORS


class EventBulkInviteView(APIView):
    permission_classes = [IsActiveStaff]

    @extend_schema(tags=["Admin events"], request=BulkInviteInputSerializer,
                   description="Requires manage_invitations and events.invites. At most 200 email-bound invites; mail contains event navigation and no admission credential.",
                   responses={201: BulkInviteResultSerializer, **ERRORS})
    def post(self, request, pk):
        event = event_authority.get_event(request.user, pk, MANAGE_INVITATIONS)
        payload = BulkInviteInputSerializer(data=request.data)
        payload.is_valid(raise_exception=True)
        return Response({"created": bulk_invites(event, request.user, **payload.validated_data)}, status=201)
