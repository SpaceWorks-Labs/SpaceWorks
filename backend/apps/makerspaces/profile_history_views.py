"""Complete the reserved event badges without changing the frozen serializers."""

from drf_spectacular.utils import OpenApiParameter, extend_schema
from rest_framework.pagination import PageNumberPagination

from .profile_history_public import event_history
from .public_profile_serializers import PublicEventPageSerializer, PublicEventSerializer
from .public_profile_views import ERRORS, REDIRECT, PublicProfileBase


class PublicProfileEventsView(PublicProfileBase):
    @extend_schema(tags=["Public profiles"], auth=[], parameters=[OpenApiParameter("page", int)],
                   responses={200: PublicEventPageSerializer, **REDIRECT, **ERRORS},
                   description="Public event history, once per event. Badge priority: SPOKE, HOSTED, ATTENDED.")
    def get(self, request, handle):
        claim, redirect = self.resolve(request, handle, "events")
        if redirect is not None:
            return redirect
        paginator = PageNumberPagination()
        paginator.page_size = 24
        rows = paginator.paginate_queryset(event_history(claim.profile), request, view=self)
        return paginator.get_paginated_response(PublicEventSerializer(rows, many=True).data)
