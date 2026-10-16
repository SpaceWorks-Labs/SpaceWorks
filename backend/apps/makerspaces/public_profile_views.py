"""Anonymous profile endpoints: one resolution gate, no public response caching."""

from drf_spectacular.utils import extend_schema, OpenApiParameter, OpenApiResponse
from rest_framework.permissions import AllowAny
from rest_framework.pagination import PageNumberPagination
from rest_framework.response import Response
from rest_framework.views import APIView
from django.utils.cache import patch_vary_headers
from apps.apiclients.throttling import ClientTierRateThrottle
from apps.accounts.authentication import SpaceWorksJWTAuthentication
from apps.hardware_requests.exceptions import ErrorSerializer
from .public_profile_access import resolve_public_profile
from .public_profile_projection import public_profile_payload, public_project, public_projects, public_events, public_event
from .public_profile_serializers import (
    PublicProfileSerializer, PublicActivitySerializer, PublicEventSerializer,
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

    def finalize_response(self, request, response, *args, **kwargs):
        response = super().finalize_response(request, response, *args, **kwargs)
        response["Cache-Control"] = "no-store"
        patch_vary_headers(response, ("Origin", "Host"))
        return response

    def resolve(self, request, handle, suffix=""):
        claim, redirected = resolve_public_profile(handle, request)
        if redirected:
            location = f"/api/v1/public/profiles/{claim.handle}/{suffix}"
            if request.META.get("QUERY_STRING"):
                location += "?" + request.META["QUERY_STRING"]
            return claim, Response(status=302, headers={"Location": location})
        return claim, None


class PublicProfileView(PublicProfileBase):
    authentication_classes = [SpaceWorksJWTAuthentication]

    @extend_schema(tags=["Public profiles"], responses={200: PublicProfileSerializer, 401: ErrorSerializer, **REDIRECT, **ERRORS})
    def get(self, request, handle):
        claim, redirect = self.resolve(request, handle)
        if redirect is not None:
            return redirect
        payload = public_profile_payload(claim)
        payload["viewer_is_owner"] = bool(request.user.is_authenticated and request.user.pk == claim.user_id)
        return Response(PublicProfileSerializer(payload).data)


class PublicProfileActivityView(PublicProfileBase):
    @extend_schema(tags=["Public profiles"], auth=[], parameters=[
        OpenApiParameter("from", str, description="First local date (inclusive)."),
        OpenApiParameter("to", str, description="Last local date (inclusive), at most 120 days."),
    ], responses={200: PublicActivitySerializer, 400: ErrorSerializer, **REDIRECT, **ERRORS})
    def get(self, request, handle):
        from .profile_activity_public import daily_activity
        claim, redirect = self.resolve(request, handle, "activity")
        if redirect is not None:
            return redirect
        return Response(PublicActivitySerializer(daily_activity(claim.profile, request.query_params)).data)


class PublicProfileEventsView(PublicProfileBase):
    @extend_schema(tags=["Public profiles"], auth=[], parameters=[OpenApiParameter("page", int)],
                   responses={200: PublicEventPageSerializer, **REDIRECT, **ERRORS})
    def get(self, request, handle):
        claim, redirect = self.resolve(request, handle, "events")
        if redirect is not None:
            return redirect
        paginator = PageNumberPagination()
        paginator.page_size = 24
        rows = paginator.paginate_queryset(public_events(claim.profile), request, view=self)
        return paginator.get_paginated_response(PublicEventSerializer(
            [public_event(row) for row in rows], many=True).data)


class PublicProfileProjectsView(PublicProfileBase):
    @extend_schema(tags=["Public profiles"], auth=[], parameters=[OpenApiParameter("page", int)],
                   responses={200: PublicProjectPageSerializer, **REDIRECT, **ERRORS})
    def get(self, request, handle):
        claim, redirect = self.resolve(request, handle, "projects")
        if redirect is not None:
            return redirect
        paginator = PageNumberPagination()
        paginator.page_size = 24
        rows = paginator.paginate_queryset(public_projects(claim.profile), request, view=self)
        return paginator.get_paginated_response(PublicProjectSerializer(
            [public_project(row) for row in rows], many=True).data)
