"""Event history for the member themselves and for the staff member drawer.

The member route deliberately does NOT require the membership module or a membership: an
account-only attendee (an `accounts` audience event, a collaborative or invited guest) owns
their registrations here and may read them, exactly as `member_may_see_own_charges` admits
an account-only borrower to their own debt. If a membership exists its status decides, so a
REVOKED member is still refused.
"""

from django.shortcuts import get_object_or_404
from drf_spectacular.utils import extend_schema
from rest_framework.exceptions import NotFound, PermissionDenied
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.accounts import rbac
from apps.admin_api.permissions import IsActiveStaff
from apps.makerspaces.guards import require_module
from apps.makerspaces.models import Makerspace, MakerspaceMembership
from apps.makerspaces.servability import servable_queryset

from .member_history import history_for_space, registrations_for_space
from .serializers_speakers import EventHistorySerializer
from .speaker_history import speaking_rows
from .views_invites import ERRORS


def _owns_history(makerspace, user):
    return (registrations_for_space(makerspace, user).exists()
            or speaking_rows(user, makerspace).exists())


def member_may_see_own_event_history(user, makerspace):
    if not (user and user.is_authenticated and user.is_active and user.access_status == "active"
            and not getattr(user, "is_tenant_dump_stub", False)):
        return False
    membership = MakerspaceMembership.objects.filter(makerspace=makerspace, user=user).first()
    if membership is not None:
        return membership.status == "active"
    return _owns_history(makerspace, user)


class MemberEventHistoryView(APIView):
    permission_classes = [IsAuthenticated]

    @extend_schema(tags=["Member events"], responses={200: EventHistorySerializer, **ERRORS},
                   description="The caller's own registrations, attendance and speaking in this makerspace. "
                               "Account-only attendees are admitted; the membership module is not required.")
    def get(self, request, makerspace_id):
        makerspace = get_object_or_404(servable_queryset(Makerspace.objects.all()), pk=makerspace_id)
        require_module(makerspace, "events")
        if not member_may_see_own_event_history(request.user, makerspace):
            raise PermissionDenied("No event history is available for this account here.")
        return Response(EventHistorySerializer(history_for_space(makerspace, request.user)).data)


class StaffMemberEventHistoryView(APIView):
    permission_classes = [IsActiveStaff]

    @extend_schema(tags=["Admin events"], responses={200: EventHistorySerializer, **ERRORS},
                   description="One person's registrations, attendance and speaking in this makerspace, for the "
                               "staff member drawer. Requires manage_events or manage_members here.")
    def get(self, request, makerspace_id, user_id):
        makerspace = get_object_or_404(Makerspace, pk=makerspace_id)
        if not (rbac.can(request.user, rbac.Action.MANAGE_EVENTS, makerspace.pk)
                or rbac.can(request.user, rbac.Action.MANAGE_MEMBERS, makerspace.pk)):
            raise PermissionDenied()
        require_module(makerspace, "events")
        from apps.accounts.models import User
        user = User.objects.filter(pk=user_id).first()
        if user is None or not (MakerspaceMembership.objects.filter(makerspace=makerspace, user=user).exists()
                                or _owns_history(makerspace, user)):
            raise NotFound("No such person in this makerspace.")
        return Response(EventHistorySerializer(history_for_space(makerspace, user)).data)
