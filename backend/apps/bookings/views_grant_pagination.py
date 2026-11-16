"""Bounded pages for resource credentials."""

from drf_spectacular.utils import OpenApiParameter
from rest_framework.pagination import PageNumberPagination

PAGE_PARAMETERS = [OpenApiParameter("page", int)]


def paginated(request, rows, serializer):
    paginator = PageNumberPagination()
    paginator.page_size = 24
    page = paginator.paginate_queryset(rows, request)
    response = paginator.get_paginated_response(serializer(page, many=True).data)
    response["Cache-Control"] = "private, no-store"
    return response
