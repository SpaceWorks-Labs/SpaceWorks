from django.utils.translation import gettext
from drf_spectacular.utils import OpenApiParameter, extend_schema
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.admin_api.permissions import IsActiveStaff
from apps.hardware_requests.exceptions import ErrorSerializer
from apps.makerspaces.origin_scope import origin_scoped_makerspace_id

from . import event_authority
from .event_permissions import VIEW
from .models import Event
from .serializers_admin import EventAdminSerializer, EventListResponseSerializer
from .serializers_event_authority import event_list_context
from .views_admin_event_detail import _EventPagination, _annotate_registration_counts


class AccessibleEventListView(APIView):
    permission_classes = [IsActiveStaff]

    @extend_schema(tags=["Admin events"], request=None,
                   parameters=[OpenApiParameter("makerspace_id", int),
                               OpenApiParameter("page", int), OpenApiParameter("page_size", int)],
                   responses={200: EventListResponseSerializer, **{code: ErrorSerializer for code in (400, 401, 403, 404)}})
    def get(self, request):
        rows = event_authority.events_for(request.user, VIEW, Event.objects.all())
        scope = origin_scoped_makerspace_id(request)
        if scope is not None:
            rows = rows.filter(makerspace_id=scope)
        selected = request.query_params.get("makerspace_id")
        if selected:
            from rest_framework.exceptions import ValidationError
            if not selected.isdecimal() or int(selected) < 1:
                raise ValidationError({"makerspace_id": gettext("Choose a valid makerspace.")})
            rows = rows.filter(makerspace_id=int(selected))
        rows = rows.filter(makerspace__enabled_modules__contains=["events"])
        rows = _annotate_registration_counts(rows).select_related("makerspace", "series").prefetch_related("organizers__organization", "audience_organizations__organization").order_by("starts_at", "id")
        paginator = _EventPagination()
        page = paginator.paginate_queryset(rows, request, view=self)
        context = event_list_context(request, page)
        return paginator.get_paginated_response(EventAdminSerializer(page, many=True, context=context).data)
