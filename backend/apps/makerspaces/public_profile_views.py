"""Anonymous profile endpoints: one resolution gate, no public response caching."""

from drf_spectacular.utils import extend_schema, OpenApiParameter, OpenApiResponse
from rest_framework.permissions import AllowAny
from rest_framework.pagination import PageNumberPagination
from rest_framework.response import Response
from rest_framework.views import APIView
from apps.apiclients.throttling import ClientTierRateThrottle
from apps.accounts.authentication import SpaceWorksJWTAuthentication
from apps.hardware_requests.exceptions import ErrorSerializer
from .account_profile_access import resolve_by_handle
from .public_profile_access import resolve_public_profile
from .account_profile_read import build_payload
from .account_profile_serializers import AccountProfileSerializer
from .public_profile_projection import public_project
from .throttles import PROFILE_LOOKUP_THROTTLES
from .public_profile_serializers import (
    PublicActivitySerializer, PublicEventSerializer,
    PublicProjectSerializer, PublicProjectPageSerializer, PublicEventPageSerializer,
)

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
    """Optional-JWT read of the GLOBAL profile by handle (decision 303).

    Signed-in callers read any visible profile; logged-out callers additionally need the open-web
    consent. Every refusal is the same 404.
    """

    authentication_classes = [SpaceWorksJWTAuthentication]
    # Signed-in callers see the member audience, so they get a per-account budget (H5);
    # anonymous callers keep `public_read` (PROFILE_LOOKUP_THROTTLES skip them).
    throttle_classes = [ClientTierRateThrottle, *PROFILE_LOOKUP_THROTTLES]

    @extend_schema(tags=["Public profiles"], responses={200: AccountProfileSerializer, 401: ErrorSerializer,
                                                         **REDIRECT, **ERRORS})
    def get(self, request, handle):
        self.cache_headers()
        profile, redirected = resolve_by_handle(handle, request.user, request)
        if redirected:
            return Response(status=302, headers={"Location": f"/api/v1/public/profiles/{redirected}/"})
        if request.user.is_authenticated and request.user.pk == profile.user_id:
            audience = "owner"
        else:
            audience = "member" if request.user.is_authenticated else "public"
        return Response(AccountProfileSerializer(build_payload(profile, audience, request.user)).data)


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
