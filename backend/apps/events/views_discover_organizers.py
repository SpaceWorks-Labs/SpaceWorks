"""Organiser picker for public event discovery (parity E-F3, A14; `events.discovery_filters`).

Answers only `slug` and `name` of public organisations behind currently discoverable events; the same rules as the
Discover list decide which events count, so no private or unlisted event can be inferred from it.
"""
from drf_spectacular.utils import OpenApiParameter, extend_schema
from rest_framework import serializers
from rest_framework.pagination import PageNumberPagination

from apps.makerspaces.website_directory import directory_spaces
from apps.makerspaces.website_views import ERRORS, WebsitePublicView

from .website_discovery import discoverable_organizers

CACHE_SECONDS = 300


class DiscoverOrganizerSerializer(serializers.Serializer):
    slug = serializers.SlugField()
    name = serializers.CharField()


class DiscoverOrganizerPageSerializer(serializers.Serializer):
    count = serializers.IntegerField()
    next = serializers.URLField(allow_null=True)
    previous = serializers.URLField(allow_null=True)
    results = DiscoverOrganizerSerializer(many=True)


class OrganizerPagination(PageNumberPagination):
    page_size = 100


class WebsiteDiscoverOrganizersView(WebsitePublicView):
    @extend_schema(tags=["Public websites"], auth=[], parameters=[OpenApiParameter("page", int)],
                   responses={200: DiscoverOrganizerPageSerializer, **ERRORS},
                   description="Public organisations organising at least one event the Discover list shows, by name. "
                               "Slug and name only; cacheable for five minutes.")
    def get(self, request):
        pager = OrganizerPagination()
        page = pager.paginate_queryset(discoverable_organizers(directory_spaces()), request, view=self)
        response = pager.get_paginated_response(DiscoverOrganizerSerializer(page, many=True).data)
        response["Cache-Control"] = f"public, max-age={CACHE_SECONDS}"
        return response
