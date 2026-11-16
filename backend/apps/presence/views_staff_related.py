from django.shortcuts import get_object_or_404
from drf_spectacular.utils import extend_schema
from rest_framework.response import Response

from apps.accounts import rbac
from .display import present_rows
from .related import related_for
from .schema import ERRORS
from .serializers_related import PresenceRelatedSerializer
from .views_staff import StaffPresenceView, staff_space


class PresenceRelatedView(StaffPresenceView):
    @extend_schema(
        tags=["Presence staff"], responses={200: PresenceRelatedSerializer, **ERRORS},
        description="Read-only. Requires manage_members in this makerspace. The event registration, booking "
                    "arrival and machine sessions around one person's live presence session; each part is "
                    "empty unless its module is on and the viewer holds that area's authority.")
    def get(self, request, makerspace_id, account_id):
        space = staff_space(request, makerspace_id)
        rows = rbac.scope_by_action(request.user, rbac.Action.MANAGE_MEMBERS, present_rows(space))
        session = get_object_or_404(rows.select_related("event_registration__event"), account_id=account_id)
        return Response(PresenceRelatedSerializer(related_for(request.user, space, session)).data)
