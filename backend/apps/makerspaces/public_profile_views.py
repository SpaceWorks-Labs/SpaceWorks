"""Anonymous profile endpoints: one resolution gate, no public response caching."""

from drf_spectacular.utils import extend_schema, OpenApiParameter, OpenApiResponse
from rest_framework.exceptions import APIException
from rest_framework.permissions import AllowAny
from rest_framework.pagination import PageNumberPagination
from rest_framework.response import Response
from rest_framework.views import APIView
from apps.apiclients.throttling import ClientTierRateThrottle
from apps.accounts.authentication import SpaceWorksJWTAuthentication
from apps.hardware_requests.exceptions import ErrorSerializer
from .account_profile_access import resolve_by_handle
from .public_profile_access import resolve_public_profile
from .public_profile_card import public_card, resolve_card_handle
from .public_profile_projection import public_project
from .public_profile_serializers import (
    PublicAccountCardSerializer, PublicActivitySerializer, PublicEventSerializer,
    PublicProjectSerializer, PublicProjectPageSerializer, PublicEventPageSerializer,
)

from .throttles import PROFILE_LOOKUP_THROTTLES


class OptionalCardAuthentication(SpaceWorksJWTAuthentication):
    """Identify verified sessions for abuse budgets, without gating public data."""

    def authenticate(self, request):
        try:
            return super().authenticate(request)
        except APIException:
            # Expired/restricted sessions may still read the anonymous public card.
            return None


ERRORS = {404: OpenApiResponse(ErrorSerializer, description="Profile not found."),
          429: OpenApiResponse(description="Request rate exceeded.")}
REDIRECT = {302: OpenApiResponse(description="Retired handle redirects to the current public handle.")}


class PublicProfileBase(APIView):
    permission_classes = [AllowAny]
    authentication_classes = []
    throttle_classes = [ClientTierRateThrottle]
    throttle_scope = "public_read"

    def cache_headers(self):
        # Called by the authenticated handler, never a DRF lifecycle override.
        # Middleware covers authentication/throttle errors before this point.
        self.headers["Cache-Control"] = "no-store"
        vary = self.headers.get("Vary", "").split(",")
        self.headers["Vary"] = ", ".join(dict.fromkeys(
            [value.strip() for value in vary if value.strip()] + ["Origin", "Host"]
        ))

    def resolve(self, request, handle, suffix=""):
        self.cache_headers()
        claim, redirected = resolve_public_profile(handle, request)
        if redirected:
            location = f"/api/v1/public/profiles/{claim.handle}/{suffix}"
            if request.META.get("QUERY_STRING"):
                location += "?" + request.META["QUERY_STRING"]
            return claim, Response(status=302, headers={"Location": location})
        return claim, None


class PublicProfileView(PublicProfileBase):
    """Always-on public card, identical for owners, signed-in viewers and visitors."""

    authentication_classes = [OptionalCardAuthentication]
    throttle_classes = [ClientTierRateThrottle, *PROFILE_LOOKUP_THROTTLES]

    @extend_schema(tags=["Public profiles"], auth=[], summary="Read the always-on public account card",
                   description="Minors and restricted/suspended accounts expose only display_name and avatar_url. "
                   "Other accounts also expose handle, bio, chosen public projects and active public memberships. "
                   "No contact details or internal identifiers are returned. Responses are no-store.",
                   responses={200: PublicAccountCardSerializer, **REDIRECT, **ERRORS})
    def get(self, request, handle):
        self.cache_headers()
        claim, redirected = resolve_card_handle(handle, request)
        if redirected:
            return Response(status=302, headers={"Location": f"/api/v1/public/profiles/{claim.handle}/"})
        return Response(PublicAccountCardSerializer(public_card(claim)).data)


class PublicProfileActivityView(PublicProfileBase):
    authentication_classes = [SpaceWorksJWTAuthentication]

    @extend_schema(tags=["Public profiles"], parameters=[
        OpenApiParameter("from", str, description="First local date (inclusive)."),
        OpenApiParameter("to", str, description="Last local date (inclusive), at most 120 days."),
    ], responses={200: PublicActivitySerializer, 400: ErrorSerializer, **REDIRECT, **ERRORS})
    def get(self, request, handle):
        from .profile_activity_public import daily_activity
        self.cache_headers()
        profile, redirected = resolve_by_handle(handle, request.user, request)
        if redirected:
            return Response(status=302, headers={"Location": f"/api/v1/public/profiles/{redirected}/activity"})
        return Response(PublicActivitySerializer(daily_activity(profile, request.query_params)).data)


class PublicProfileEventsView(PublicProfileBase):
    authentication_classes = [SpaceWorksJWTAuthentication]

    @extend_schema(tags=["Public profiles"], parameters=[OpenApiParameter("page", int)],
                   responses={200: PublicEventPageSerializer, **REDIRECT, **ERRORS})
    def get(self, request, handle):
        self.cache_headers()
        profile, redirected = resolve_by_handle(handle, request.user, request)
        if redirected:
            return Response(status=302, headers={"Location": f"/api/v1/public/profiles/{redirected}/events"})
        from .profile_history_public import event_history
        rows = event_history(profile)
        paginator = PageNumberPagination()
        paginator.page_size = 24
        page = paginator.paginate_queryset(rows, request, view=self)
        return paginator.get_paginated_response(PublicEventSerializer(page, many=True).data)


class PublicProfileProjectsView(PublicProfileBase):
    authentication_classes = [SpaceWorksJWTAuthentication]

    @extend_schema(tags=["Public profiles"], parameters=[OpenApiParameter("page", int)],
                   responses={200: PublicProjectPageSerializer, **REDIRECT, **ERRORS})
    def get(self, request, handle):
        self.cache_headers()
        profile, redirected = resolve_by_handle(handle, request.user, request)
        if redirected:
            return Response(status=302, headers={"Location": f"/api/v1/public/profiles/{redirected}/projects"})
        rows = profile.projects.filter(public_visible=True) if profile.show_projects else []
        paginator = PageNumberPagination()
        paginator.page_size = 24
        page = paginator.paginate_queryset(rows, request, view=self)
        return paginator.get_paginated_response(PublicProjectSerializer(
            [public_project(row) for row in page], many=True).data)
