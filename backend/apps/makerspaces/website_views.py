"""Shared embed, share, crawler and discover serving; no domain imports."""

from dataclasses import asdict
from xml.sax.saxutils import escape

from django.http import HttpResponse
from drf_spectacular.utils import OpenApiParameter, OpenApiResponse, extend_schema
from rest_framework import serializers
from rest_framework.pagination import PageNumberPagination
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.apiclients.throttling import ClientTierRateThrottle
from apps.hardware_requests.exceptions import ErrorSerializer
from .platform import feature_enabled
from .website_directory import directory_spaces, sitemap_spaces
from .website_serving import embed_response, share_response
from .website_visibility import adapter_for, adapters

ERRORS = {code: OpenApiResponse(ErrorSerializer, description=text) for code, text in (
    (400, "Invalid discovery filters."), (404, "Unknown or unavailable public content."),
    (429, "Rate limit exceeded."),
)}


class DiscoveryFilters(serializers.Serializer):
    q = serializers.CharField(max_length=200, allow_blank=True, required=False)
    date_from = serializers.DateField(required=False)
    date_to = serializers.DateField(required=False)

    def validate(self, data):
        if data.get("date_from") and data.get("date_to") and data["date_from"] > data["date_to"]:
            raise serializers.ValidationError("The end date must follow the start date.")
        return data


class DiscoveryCardSerializer(serializers.Serializer):
    title = serializers.CharField()
    description = serializers.CharField()
    url = serializers.URLField()
    image_url = serializers.URLField(allow_null=True)
    image_alt = serializers.CharField(allow_blank=True)
    date = serializers.CharField()
    location = serializers.CharField()
    availability = serializers.CharField()
    audience_label = serializers.CharField()
    revision = serializers.CharField()
    registration_count = serializers.IntegerField(allow_null=True)
    makerspace_name = serializers.CharField()


class DiscoverySerializer(serializers.Serializer):
    count = serializers.IntegerField()
    next = serializers.URLField(allow_null=True)
    previous = serializers.URLField(allow_null=True)
    results = DiscoveryCardSerializer(many=True)


class WebsitePublicView(APIView):
    permission_classes = [AllowAny]
    authentication_classes = []
    throttle_classes = [ClientTierRateThrottle]
    throttle_scope = "public_read"


class WebsiteEmbedView(WebsitePublicView):
    @extend_schema(tags=["Public websites"], auth=[], responses={200: OpenApiResponse(str, description="Self-contained HTML with exact framing CSP."), **ERRORS})
    def get(self, request, makerspace_slug, kind, public_token):
        adapter = adapter_for(kind)
        subject = adapter.resolve(makerspace_slug, public_token)
        adapter.page(subject)
        if not feature_enabled(subject.makerspace, f"{adapter.module}.embed"):
            from django.http import Http404
            raise Http404
        return embed_response(adapter.card(subject), subject.makerspace.website_embed_origins,
                              action_label=adapter.action_label)


class WebsiteShareView(WebsitePublicView):
    @extend_schema(tags=["Public websites"], auth=[], responses={200: OpenApiResponse(str, description="Noindex HTML with public OG/Twitter metadata; server cache 600s, live-gated."), **ERRORS})
    def get(self, request, kind, public_token):
        adapter = adapter_for(kind)
        subject = adapter.resolve(None, public_token)
        adapter.page(subject)
        return share_response(adapter.card(subject))


class WebsiteDiscoverView(WebsitePublicView):
    @extend_schema(tags=["Public websites"], auth=[], parameters=[DiscoveryFilters,
        OpenApiParameter("kind", str, description="Booking resource kind (query filter); events use date filters instead."),
        OpenApiParameter("location", str, description="Booking resource location contains this text."),
    ], responses={200: DiscoverySerializer, **ERRORS})
    def get(self, request, kind):
        adapter = adapter_for(kind)
        filters = (adapter.filters or DiscoveryFilters)(data=request.query_params)
        filters.is_valid(raise_exception=True)
        rows = adapter.discover(directory_spaces(), filters.validated_data)
        paginator = PageNumberPagination()
        paginator.page_size = 24
        page = paginator.paginate_queryset(rows, request)
        cards = adapter.cards(page) if adapter.cards else [adapter.card(row) for row in page]
        response = paginator.get_paginated_response([asdict(card) for card in cards])
        response["Cache-Control"] = "no-store"
        return response


class WebsiteSitemapView(WebsitePublicView):
    @extend_schema(tags=["Public websites"], auth=[], responses={200: OpenApiResponse(str, description="Origin-scoped XML sitemap of live public subjects."), **ERRORS})
    def get(self, request):
        from .website_directory import public_url
        urls = []
        spaces = sitemap_spaces(request)
        for adapter in adapters():
            for row in adapter.discover(spaces, {})[:50000 - len(urls)]:
                if adapter.kind == "events":
                    from .public_page_access import canonical_origin
                    urls.append(f"{canonical_origin(row.makerspace)}/e/{row.public_token}")
                else:
                    urls.append(public_url(row.makerspace, adapter.kind, row.public_token))
        from itertools import islice
        from .public_profile_share import sitemap_profile_urls
        urls.extend(islice(sitemap_profile_urls(request, spaces=spaces), max(0, 50000 - len(urls))))
        from .public_page_share import sitemap_page_urls
        urls.extend(islice(sitemap_page_urls(request, spaces=spaces), max(0, 50000 - len(urls))))
        urls = list(dict.fromkeys(urls))
        body = '<?xml version="1.0" encoding="UTF-8"?><urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">'
        body += "".join(f"<url><loc>{escape(url)}</loc></url>" for url in urls)
        response = HttpResponse(body + "</urlset>", content_type="application/xml")
        response["Cache-Control"] = "no-store"
        return response


class WebsiteRobotsView(WebsitePublicView):
    @extend_schema(tags=["Public websites"], auth=[], responses={200: OpenApiResponse(str, description="Public crawler policy and origin sitemap."), **ERRORS})
    def get(self, request):
        sitemap_spaces(request)  # Same known-origin policy, never trust an arbitrary Host.
        body = "User-agent: *\nDisallow: /admin\nDisallow: /member\nDisallow: /share/\nDisallow: /embed/\n"
        body += f"Sitemap: {request.build_absolute_uri('/sitemap.xml')}\n"
        return HttpResponse(body, content_type="text/plain")
