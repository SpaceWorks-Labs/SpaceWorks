from rest_framework.response import Response
from rest_framework.views import APIView
from drf_spectacular.utils import extend_schema

from apps.accounts.models import User
from apps.admin_api.permissions import IsActiveStaff
from apps.events.event_permissions import MANAGE_REGISTRATIONS
from apps.events.models import EventRegistration
from apps.events.serializers_admin import EventEligibleMemberSerializer
from apps.events.views_admin_event_detail import _manageable_event
from apps.makerspaces.models import MakerspaceMembership
from .registration_view_errors import REGISTRATION_ACTION_ERRORS


class EventEligibleMemberListView(APIView):
    """The roster the staff registration picker reads.

    Hung off the EVENT rather than the makerspace, so it inherits `_manageable_event`
    and introduces no new authority question: whoever may manage this event may see who
    they can register for it. A separate makerspace-level member list would have needed
    its own permission answer, and the obvious candidates were all wrong — the
    direct-loan roster is gated on `ISSUE_DIRECT_LOAN` plus a self-checkout feature an
    events manager need not hold, and the full membership list is `MANAGE_MAKERSPACE`.

    Already-registered members are excluded: offering someone the picker can only reject
    as a duplicate is an error the interface should not have made available.
    """

    permission_classes = [IsActiveStaff]

    @extend_schema(
        tags=['Admin events'],
        summary='List members who can be registered for an event',
        request=None,
        responses={200: EventEligibleMemberSerializer(many=True), **REGISTRATION_ACTION_ERRORS},
    )
    def get(self, request, pk, *args, **kwargs):
        event = _manageable_event(request.user, pk, MANAGE_REGISTRATIONS)
        registered = EventRegistration.objects.filter(event=event, member_id__isnull=False).exclude(
            status=EventRegistration.Status.CANCELLED
        ).values_list('member_id', flat=True)
        from .organization_audience import AUDIENCE, eligible_event_accounts
        if event.registration_audience == AUDIENCE:
            accounts = eligible_event_accounts(event).exclude(pk__in=registered).order_by("display_name", "pk")
            return Response(EventEligibleMemberSerializer([
                {"member_id": user.pk, "display_name": user.display_name or user.username}
                for user in accounts
            ], many=True).data)
        memberships = MakerspaceMembership.objects.select_related('user').filter(
            makerspace=event.makerspace, status='active', user__is_active=True,
            user__account_kind=User.AccountKind.MEMBER,
            user__access_status=User.AccessStatus.ACTIVE,
        ).exclude(user_id__in=registered).order_by(
            'user__display_name', 'user__username'
        )
        return Response(
            EventEligibleMemberSerializer(
                [
                    {
                        'member_id': membership.user_id,
                        'display_name': (
                            membership.user.display_name or membership.user.username
                        ),
                    }
                    for membership in memberships
                ],
                many=True,
            ).data
        )
