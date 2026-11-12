"""Typed public JSON; private snapshots and object keys never cross this boundary."""

from django.shortcuts import get_object_or_404
from drf_spectacular.utils import OpenApiResponse, extend_schema
from rest_framework.response import Response
from apps.accounts.authentication import SpaceWorksJWTAuthentication
from .public_profile_views import PublicProfileBase
from .models import Makerspace
from .public_page_access import public_page, resolve_handle
from .public_page_projection import projection
from .public_page_serializers import HandleResolution, PublicPageProjection, PageEventQuery

ERRORS = {404: OpenApiResponse(description="Unknown or unavailable public page."),
          429: OpenApiResponse(description="Rate limit exceeded.")}


class PublicHandleView(PublicProfileBase):
    """Optional JWT: a signed-in viewer resolves any visible member handle (decision 303a)."""

    authentication_classes = [SpaceWorksJWTAuthentication]

    @extend_schema(tags=["Public pages"], auth=[], responses={200: HandleResolution, **ERRORS})
    def get(self, request, handle):
        self.cache_headers()
        viewer = request.user if request.user.is_authenticated else None
        if viewer is not None:
            self.headers["Cache-Control"] = "private, no-store"
            self.headers["Vary"] = f'{self.headers["Vary"]}, Authorization'
        _, payload = resolve_handle(handle, request, viewer)
        return Response(HandleResolution(payload).data)


class PublicPageView(PublicProfileBase):
    @extend_schema(tags=["Public pages"], auth=[], parameters=[PageEventQuery],
                   responses={200: PublicPageProjection, 400: OpenApiResponse(description="Invalid events_page."), **ERRORS})
    def get(self, request, makerspace_slug=None, slug=None, kind="makerspace"):
        self.cache_headers()
        query = PageEventQuery(data=request.query_params)
        query.is_valid(raise_exception=True)
        if kind == "makerspace":
            owner = get_object_or_404(Makerspace, slug=makerspace_slug)
        else:
            from apps.organizations.models import Organization
            owner = get_object_or_404(Organization, slug=slug)
        page = public_page(kind, owner, request)
        return Response(PublicPageProjection(projection(kind, owner, page, request=request)).data)
