"""Live authorized resources for mixed event/booking grant workspaces."""

from django.utils.translation import gettext
from drf_spectacular.utils import OpenApiParameter, extend_schema
from rest_framework.exceptions import ValidationError
from rest_framework.views import APIView

from apps.admin_api.permissions import IsActiveStaff
from apps.hardware_requests.exceptions import ErrorSerializer
from apps.makerspaces.origin_scope import origin_scoped_makerspace_id

from . import booking_authority
from .serializers_admin import BookableSpaceAdminSerializer, BookableSpaceListResponseSerializer
from .views_admin_space_detail import _SpacePagination, _page_response


class AccessibleSpaceListView(APIView):
    permission_classes = [IsActiveStaff]

    @extend_schema(tags=["Admin bookings"], request=None,
                   parameters=[OpenApiParameter("makerspace_id", int), OpenApiParameter("page", int)],
                   responses={200: BookableSpaceListResponseSerializer,
                              **{code: ErrorSerializer for code in (400, 401, 403, 404)}})
    def get(self, request):
        rows = booking_authority.spaces_for(request.user, "view").select_related("makerspace")
        scope = origin_scoped_makerspace_id(request)
        if scope is not None:
            rows = rows.filter(makerspace_id=scope)
        selected = request.query_params.get("makerspace_id")
        if selected:
            if not selected.isdecimal() or not 0 < int(selected) <= 9223372036854775807:
                raise ValidationError({"makerspace_id": gettext("Choose a valid makerspace.")})
            rows = rows.filter(makerspace_id=int(selected))
        paginator = _SpacePagination()
        page = paginator.paginate_queryset(rows.order_by("name", "pk"), request, view=self)
        return _page_response(paginator, page, BookableSpaceAdminSerializer, request.user)
