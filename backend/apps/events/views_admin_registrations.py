from django.shortcuts import get_object_or_404
from drf_spectacular.utils import OpenApiResponse, PolymorphicProxySerializer, extend_schema
from rest_framework import status
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.accounts import rbac
from apps.accounts.models import User
from apps.admin_api.permissions import IsActiveStaff
from apps.admin_api.serializers_payment_summary import scoped_payment_context
from apps.events import services
from apps.events import event_authority
from apps.events.models import EventRegistration
from apps.events.event_permissions import MANAGE_REGISTRATIONS, CHECK_IN
from apps.events.services_registration_tools import annotate_registration_restore_history
from apps.events.serializers_checkin import EventCheckInResultSerializer
from apps.events.serializers_admin import (
    EventAttendanceMarkSerializer,
    EmptyActionSerializer,
    EventEligibleMemberSerializer,
    EventRegistrationAdminSerializer,
    EventRegistrationListResponseSerializer,
    EventStaffRegistrationSerializer,
)
from apps.events.views_admin_events import (
    EVENT_ERROR_409,
    EVENT_VALIDATION_ERROR_SCHEMA,
    _manageable_event,
    _manageable_registration,
    _paginated_response,
    _RegistrationPagination,
    _validate_empty_action,
)
from apps.hardware_requests.exceptions import ErrorSerializer
from apps.makerspaces.models import MakerspaceMembership
from apps.payments.models import Payment


from .registration_view_errors import REGISTRATION_ACTION_ERRORS


class EventRegistrationListView(APIView):
    permission_classes = [IsActiveStaff]

    @extend_schema(
        tags=['Admin events'],
        summary='List event registrations',
        request=None,
        responses={200: EventRegistrationListResponseSerializer, **REGISTRATION_ACTION_ERRORS},
    )
    def get(self, request, pk, *args, **kwargs):
        event = _manageable_event(request.user, pk, MANAGE_REGISTRATIONS)
        queryset = annotate_registration_restore_history(
            EventRegistration.objects.filter(event=event).order_by('created_at', 'id')
        )
        paginator = _RegistrationPagination()
        page = paginator.paginate_queryset(queryset, request, view=self)
        from .organization_audience import annotate_roster_eligibility
        annotate_roster_eligibility(event, page)
        context = scoped_payment_context(
            request.user,
            rbac.Action.MANAGE_EVENTS,
            Payment.SubjectType.EVENT_REGISTRATION,
            [registration.pk for registration in page],
        )
        return _paginated_response(
            paginator,
            page,
            lambda rows, many: EventRegistrationAdminSerializer(
                rows,
                many=many,
                context=context,
            ),
        )

    # Registering someone from the console goes through the SAME
    # `services_registration.register` as public self-registration: capacity,
    # waitlisting, duplicate handling, the custom form, the write fence and the
    # registration charge are one implementation, as the request-workflow rule requires
    # of every state machine here.
    #
    # Takes a `member_id` rather than free-text contact fields. Registering someone
    # means naming a real person, and a person with no account is given one at the
    # counter (`walk_in_services`) first — so there is one identity path, instead of the
    # events surface minting half-identified attendees of its own.

    @extend_schema(
        tags=['Admin events'],
        summary='Register a member for an event',
        request=EventStaffRegistrationSerializer,
        responses={
            201: EventRegistrationAdminSerializer,
            400: OpenApiResponse(ErrorSerializer, description='Invalid registration.'),
            401: ErrorSerializer, 403: ErrorSerializer, 404: ErrorSerializer,
            409: EVENT_ERROR_409,
        },
    )
    def post(self, request, pk, *args, **kwargs):
        event = _manageable_event(request.user, pk, MANAGE_REGISTRATIONS)
        serializer = EventStaffRegistrationSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        if event.registration_audience != "members":
            account = get_object_or_404(User.objects.filter(account_kind=User.AccountKind.MEMBER,
                is_active=True, access_status=User.AccessStatus.ACTIVE), pk=serializer.validated_data["member_id"])
        else:
            account = get_object_or_404(
                MakerspaceMembership.objects.select_related('user').filter(
                    makerspace=event.makerspace,
                    user_id=serializer.validated_data['member_id'],
                    status='active',
                    user__is_active=True,
                    user__account_kind=User.AccountKind.MEMBER,
                    # Account standing, not just the membership row: a restricted or
                    # suspended account is blocked everywhere else and must be blocked here
                    # too, or the console becomes the way around an access restriction.
                    user__access_status=User.AccessStatus.ACTIVE,
                )
            ).user
        registration = services.register(
            event,
            member=account,
            invite_code=serializer.validated_data.get("invite_code"),
            ticket_type_id=serializer.validated_data.get("ticket_type_id"),
            promo_code=serializer.validated_data.get("promo_code"),
            phone=serializer.validated_data.get('phone', ''),
            email=serializer.validated_data.get('email', ''),
            custom_answers=serializer.validated_data.get('custom_answers'),
            actor=request.user,
            staff_registration=True,
        )
        context = scoped_payment_context(
            request.user,
            rbac.Action.MANAGE_EVENTS,
            Payment.SubjectType.EVENT_REGISTRATION,
            [registration.pk],
        )
        return Response(
            EventRegistrationAdminSerializer(registration, context=context).data,
            status=status.HTTP_201_CREATED,
        )


class EventRegistrationMarkAttendedView(APIView):
    permission_classes = [IsActiveStaff]

    @extend_schema(
        tags=['Admin events'],
        summary='Mark an event registration attended',
        request=EventAttendanceMarkSerializer,
        responses={200: PolymorphicProxySerializer(
            component_name="EventAttendanceResult",
            serializers=[EventRegistrationAdminSerializer, EventCheckInResultSerializer],
            resource_type_field_name=None,
        ), **REGISTRATION_ACTION_ERRORS},
    )
    def post(self, request, pk, *args, **kwargs):
        registration = _manageable_registration(request.user, pk, CHECK_IN)
        serializer = EventAttendanceMarkSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        registration = services.mark_attended(
            registration,
            actor=request.user,
            source=serializer.validated_data["source"],
        )
        if not event_authority.can(request.user, registration.event, MANAGE_REGISTRATIONS):
            return Response(EventCheckInResultSerializer(registration).data)
        context = scoped_payment_context(
            request.user,
            rbac.Action.MANAGE_EVENTS,
            Payment.SubjectType.EVENT_REGISTRATION,
            [registration.pk],
        )
        return Response(
            EventRegistrationAdminSerializer(
                registration,
                context=context,
            ).data
        )


class _RegistrationActionView(APIView):
    permission_classes = [IsActiveStaff]
    operation = None

    def execute(self, request, pk):
        registration = _manageable_registration(request.user, pk, MANAGE_REGISTRATIONS)
        _validate_empty_action(request)
        registration = self.operation(registration, actor=request.user)
        context = scoped_payment_context(
            request.user,
            rbac.Action.MANAGE_EVENTS,
            Payment.SubjectType.EVENT_REGISTRATION,
            [registration.pk],
        )
        return Response(
            EventRegistrationAdminSerializer(registration, context=context).data
        )


class EventRegistrationApproveView(_RegistrationActionView):
    operation = staticmethod(services.approve_registration)

    @extend_schema(
        tags=['Admin events'],
        summary='Approve a pending event registration',
        request=EmptyActionSerializer,
        responses={200: EventRegistrationAdminSerializer, **REGISTRATION_ACTION_ERRORS},
    )
    def post(self, request, pk, *args, **kwargs):
        return self.execute(request, pk)


class EventRegistrationRejectView(_RegistrationActionView):
    operation = staticmethod(services.reject_registration)

    @extend_schema(
        tags=['Admin events'],
        summary='Reject a pending or waitlisted event registration',
        request=EmptyActionSerializer,
        responses={200: EventRegistrationAdminSerializer, **REGISTRATION_ACTION_ERRORS},
    )
    def post(self, request, pk, *args, **kwargs):
        return self.execute(request, pk)


class EventRegistrationPromoteView(_RegistrationActionView):
    operation = staticmethod(services.promote_registration)

    @extend_schema(
        tags=['Admin events'],
        summary='Manually promote an approved waitlisted registration',
        request=EmptyActionSerializer,
        responses={200: EventRegistrationAdminSerializer, **REGISTRATION_ACTION_ERRORS},
    )
    def post(self, request, pk, *args, **kwargs):
        return self.execute(request, pk)


class EventRegistrationCancelView(_RegistrationActionView):
    operation = staticmethod(services.cancel_registration)

    @extend_schema(
        tags=['Admin events'],
        summary='Cancel an event registration and release its pending charge',
        request=EmptyActionSerializer,
        responses={200: EventRegistrationAdminSerializer, **REGISTRATION_ACTION_ERRORS},
    )
    def post(self, request, pk, *args, **kwargs):
        return self.execute(request, pk)


from .views_admin_eligible_members import EventEligibleMemberListView
