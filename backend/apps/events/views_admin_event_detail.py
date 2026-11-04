from .serializers_website_publish import EventWebsitePublishInput
from django.db.models import Count, Q
from django.shortcuts import get_object_or_404
from drf_spectacular.utils import OpenApiParameter, OpenApiResponse, extend_schema
from rest_framework import status
from rest_framework.exceptions import PermissionDenied
from rest_framework.pagination import PageNumberPagination
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.inventory.search import apply_q
from apps.accounts import rbac
from apps.accounts.models import User
from apps.admin_api.permissions import IsActiveStaff
from apps.events.serializers_admin import (
    EmptyActionSerializer,
    EventAdminSerializer,
    EventListResponseSerializer,
    EventRegistrationAdminSerializer,
    EventEligibleMemberSerializer,
    EventRegistrationListResponseSerializer,
    EventStaffRegistrationSerializer,
    EventWriteSerializer,
)
from apps.admin_api.serializers_payment_summary import scoped_payment_context
from apps.events import services
from apps.events.models import Event, EventRegistration
from apps.events import event_authority
from apps.events.event_permissions import EDIT_DETAILS, PUBLISH_SCHEDULE, VIEW
from apps.hardware_requests.exceptions import ErrorSerializer
from apps.makerspaces.guards import require_module
from apps.makerspaces.models import Makerspace, MakerspaceMembership
from apps.payments.models import Payment


EVENT_VALIDATION_ERROR_SCHEMA = {'type': 'object', 'additionalProperties': {}}
EVENT_ERROR_400 = OpenApiResponse(
    EVENT_VALIDATION_ERROR_SCHEMA,
    description='Invalid event details.',
)
EVENT_ERROR_409 = OpenApiResponse(
    ErrorSerializer,
    description='Event state or capacity conflict.',
)
EVENT_SCOPED_ERRORS = {code: ErrorSerializer for code in (400, 401, 403, 404, 423, 503)}


class _EventPagination(PageNumberPagination):
    page_size = 24
    page_size_query_param = 'page_size'
    max_page_size = 200


class _RegistrationPagination(PageNumberPagination):
    page_size = 100
    page_size_query_param = 'page_size'
    max_page_size = 500


def _visible_makerspace(actor, makerspace_id):
    makerspace = get_object_or_404(
        rbac.scope_by_visibility_or_action(
            actor,
            rbac.Action.MANAGE_EVENTS,
            Makerspace.objects.all(),
            field='id',
        ),
        pk=makerspace_id,
    )
    event_authority.require_tenant(actor, makerspace)
    return makerspace


def _manageable_event(actor, pk, permission=None):
    return event_authority.get_event(actor, pk, permission)


def _manageable_registration(actor, pk, permission=None):
    registration = get_object_or_404(
        EventRegistration.objects.select_related('event__makerspace').filter(
            event_id__in=event_authority.visible_events(actor, Event.objects.all()).values('pk'),
        ), pk=pk,
    )
    event_authority.require(actor, registration.event, permission)
    return registration


def _annotate_registration_counts(queryset):
    return queryset.annotate(
        **{
            f'{value}_count': Count(
                'registrations',
                filter=Q(registrations__status=value),
            )
            for value in EventRegistration.Status.values
        }
    )


def _paginated_response(paginator, page, serializer):
    return Response(
        {
            'count': paginator.page.paginator.count,
            'next': paginator.get_next_link(),
            'previous': paginator.get_previous_link(),
            'results': serializer(page, many=True).data,
        }
    )


def _validate_empty_action(request):
    serializer = EmptyActionSerializer(data=request.data)
    serializer.is_valid(raise_exception=True)




class EventDetailView(APIView):
    permission_classes = [IsActiveStaff]

    @extend_schema(
        tags=['Admin events'],
        summary='Retrieve an event',
        request=None,
        responses={200: EventAdminSerializer, **EVENT_SCOPED_ERRORS},
    )
    def get(self, request, pk, *args, **kwargs):
        return Response(EventAdminSerializer(_manageable_event(request.user, pk, VIEW), context={"request": request}).data)

    @extend_schema(
        tags=['Admin events'],
        summary='Update an event',
        request=EventWriteSerializer,
        responses={
            200: EventAdminSerializer,
            400: EVENT_ERROR_400,
            409: EVENT_ERROR_409,
    423: OpenApiResponse(ErrorSerializer, description="Source or protected writes are fenced."),
    503: OpenApiResponse(ErrorSerializer, description="Private data or programme dependency unavailable."),
            **{code: ErrorSerializer for code in (401, 403, 404, 423, 503)},
        },
    )
    def patch(self, request, pk, *args, **kwargs):
        event = _manageable_event(request.user, pk, VIEW)
        serializer = EventWriteSerializer(event, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        values = serializer.validated_data
        fields = (set(values) - {"inherit_fields"}) | set(values.get("inherit_fields", []))
        schedule_fields = {"starts_at", "ends_at"}
        if fields & schedule_fields:
            event_authority.require(request.user, event, PUBLISH_SCHEDULE)
        if fields - schedule_fields or not fields:
            event_authority.require(request.user, event, EDIT_DETAILS)
        if not event_authority.can_manage_grants(request.user, event):
            if ("payment_amount" in serializer.validated_data
                    or "payment_amount" in serializer.validated_data.get("inherit_fields", [])):
                raise PermissionDenied()
        values = dict(serializer.validated_data)
        online = {key: values.pop(key) for key in ("delivery_mode", "join_url") if key in values}
        if online:
            # Both writes are outermost event commands (they prepare credentials before
            # locks), so refuse a switched-off change up front instead of half-applying.
            from .online_delivery import refuse_when_off
            refuse_when_off(event, online.get("delivery_mode"), online.get("join_url"))
        if values or not online:
            event = services.update_event(event, actor=request.user, **values)
        if online:
            from .online_delivery import set_online
            event = set_online(event, actor=request.user, delivery_mode=online.get("delivery_mode"),
                               join_url_value=online.get("join_url"))
        return Response(EventAdminSerializer(event, context={"request": request}).data)


class _EventActionView(APIView):
    permission_classes = [IsActiveStaff]
    operation = None

    def execute(self, request, pk):
        event = _manageable_event(request.user, pk, PUBLISH_SCHEDULE)
        _validate_empty_action(request)
        event = self.operation(event, actor=request.user)
        return Response(EventAdminSerializer(event, context={"request": request}).data)


class EventPublishView(_EventActionView):
    operation = staticmethod(services.publish)

    @extend_schema(
        tags=['Admin events'],
        summary='Publish an event',
        request=EventWebsitePublishInput,
        responses={200: EventAdminSerializer, **EVENT_SCOPED_ERRORS, 400: EVENT_ERROR_400, 409: EVENT_ERROR_409},
    )
    def post(self, request, pk, *args, **kwargs):
        event = _manageable_event(request.user, pk, PUBLISH_SCHEDULE)
        serializer = EventWebsitePublishInput(data=request.data)
        serializer.is_valid(raise_exception=True)
        event = services.publish(event, actor=request.user, **serializer.validated_data)
        return Response(EventAdminSerializer(event, context={"request": request}).data)


class EventCancelView(_EventActionView):
    operation = staticmethod(services.cancel)

    @extend_schema(
        tags=['Admin events'],
        summary='Cancel an event',
        request=EmptyActionSerializer,
        responses={200: EventAdminSerializer, **EVENT_SCOPED_ERRORS, 409: EVENT_ERROR_409},
    )
    def post(self, request, pk, *args, **kwargs):
        return self.execute(request, pk)


class EventCompleteView(_EventActionView):
    operation = staticmethod(services.complete)

    @extend_schema(
        tags=['Admin events'],
        summary='Complete an event',
        request=EmptyActionSerializer,
        responses={200: EventAdminSerializer, **EVENT_SCOPED_ERRORS, 409: EVENT_ERROR_409},
    )
    def post(self, request, pk, *args, **kwargs):
        return self.execute(request, pk)
