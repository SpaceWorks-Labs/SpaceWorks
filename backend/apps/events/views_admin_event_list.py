from drf_spectacular.utils import OpenApiParameter, extend_schema
from rest_framework import status
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.accounts import rbac
from apps.events import event_authority
from apps.admin_api.permissions import IsActiveStaff
from apps.events import services
from apps.events.models import Event
from apps.events.serializers_admin import EventAdminSerializer, EventCreateSerializer, EventListWithDefaultsSerializer
from apps.events.serializers_event_authority import event_list_context
from apps.inventory.search import apply_q
from .views_admin_event_detail import (
    _visible_makerspace,
    _annotate_registration_counts,
    _EventPagination,
    _paginated_response,
    EVENT_ERROR_400,
)
from apps.admin_api.list_options import LIST_PARAMETERS, choice_filter, order_list
from apps.hardware_requests.exceptions import ErrorSerializer


class EventListCreateView(APIView):
    permission_classes = [IsActiveStaff]

    @extend_schema(
        tags=['Admin events'],
        summary='List events in a makerspace',
        request=None,
        parameters=[
            *LIST_PARAMETERS,
            OpenApiParameter("status", str, enum=Event.Status.values),
        ],
        responses={200: EventListWithDefaultsSerializer, **{code: ErrorSerializer for code in (400, 401, 403, 404)}},
    )
    def get(self, request, makerspace_id, *args, **kwargs):
        makerspace = _visible_makerspace(request.user, makerspace_id)
        queryset = event_authority.events_for(
            request.user,
            None,
            Event.objects.filter(makerspace=makerspace),
        )
        queryset = (
            _annotate_registration_counts(queryset)
            .select_related('series')
            .prefetch_related('organizers__organization', 'audience_organizations__organization')
            .order_by('starts_at', 'id')
        )
        query = request.query_params.get('q', '')
        if query.strip():
            queryset = apply_q(queryset, query, label_field='title')
        selected_status = choice_filter(request.query_params, "status", Event.Status.values)
        if selected_status:
            queryset = queryset.filter(status=selected_status)
        queryset = order_list(queryset, request.query_params, {"starts_at", "title", "status", "created_at"}, "starts_at")
        paginator = _EventPagination()
        page = paginator.paginate_queryset(queryset, request, view=self)
        context = event_list_context(request, page)
        response = _paginated_response(
            paginator, page,
            lambda rows, many: EventAdminSerializer(rows, many=many, context=context),
        )
        response.data["default_registration_audience"] = makerspace.event_default_registration_audience
        return response

    @extend_schema(
        tags=['Admin events'],
        summary='Create a draft event',
        description=(
            "Optional organization_ids (the actor's own organizations), "
            'audience_organization_ids (from the organization directory) and '
            'collaborator_slugs (partner makerspaces to invite) are applied in the same '
            'transaction as the event; any refusal creates nothing.'
        ),
        request=EventCreateSerializer,
        responses={
            201: EventAdminSerializer,
            400: EVENT_ERROR_400,
            **{code: ErrorSerializer for code in (401, 403, 404)},
        },
    )
    def post(self, request, makerspace_id, *args, **kwargs):
        makerspace = _visible_makerspace(request.user, makerspace_id)
        serializer = EventCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        values = dict(serializer.validated_data)
        values.pop('inherit_fields', None)
        host_id = values.pop('host_makerspace_id', None)
        if host_id is not None and host_id != makerspace.pk:
            # DY-63: host in another space where the actor holds event authority.
            from .directories import require_host
            makerspace = _visible_makerspace(request.user, require_host(request.user, request, host_id).pk)
        event = services.create_event(
            makerspace=makerspace,
            actor=request.user,
            **values,
        )
        return Response(
            EventAdminSerializer(event, context={"request": request}).data,
            status=status.HTTP_201_CREATED,
        )
