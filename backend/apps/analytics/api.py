"""Analytics routes: one set per space (``admin/makerspaces/<id>/analytics/...``) and one for
the platform (``admin/platform/analytics/...``), sharing every handler. Failures the
console must explain (not available here, could not create the login, not configured) are
typed 409/503 bodies, never a 500."""

from drf_spectacular.utils import OpenApiResponse, extend_schema
from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.openapi_errors import errors

from . import access, services
from .serializers import (
    MetabaseConnectionSerializer, MetabaseConnectionUpdateSerializer, MetabaseCredentialsSerializer,
    MetabaseEmbedSerializer, MetabaseErrorSerializer, MetabaseSummarySerializer,
)

TAGS = ["Analytics"]
_CONFLICT = OpenApiResponse(MetabaseErrorSerializer, description=(
    "analytics_not_available, analytics_login_exists, analytics_login_missing, analytics_not_configured "
    "or analytics_dashboard_unknown."))
_FAILED = OpenApiResponse(MetabaseErrorSerializer, description="analytics_login_failed: the database refused.")


def _error(exc):
    code = status.HTTP_503_SERVICE_UNAVAILABLE if exc.code == "analytics_login_failed" else status.HTTP_409_CONFLICT
    return Response({"code": exc.code, "detail": exc.detail}, status=code)


def _private(response):
    response["Cache-Control"] = "no-store"
    return response


class _Scoped(APIView):
    permission_classes = [IsAuthenticated]
    platform = False

    def viewer(self, request, kwargs):
        return access.platform_scope(request.user) if self.platform else access.viewer_scope(
            request.user, kwargs["makerspace_id"])

    def manager(self, request, kwargs):
        return access.platform_scope(request.user) if self.platform else access.manager_scope(
            request.user, kwargs["makerspace_id"])


class AnalyticsSummaryView(_Scoped):
    @extend_schema(tags=TAGS, summary="Analytics dashboards available to the viewer", request=None,
                   description="view_analytics in the space (or the superadmin for the platform). 404 when the "
                               "analytics module is off. Never returns a secret.",
                   responses={200: MetabaseSummarySerializer, **errors(401, 403, 404)})
    def get(self, request, **kwargs):
        scope = self.viewer(request, kwargs)
        body = {**services.summary(scope), "can_manage": access.can_manage(request.user, scope)}
        return Response(MetabaseSummarySerializer(body).data)


class AnalyticsConnectionView(_Scoped):
    @extend_schema(tags=TAGS, summary="Read the Metabase connection and the login state", request=None,
                   description="Space Manager of the space or the superadmin. Audited as a credentials view. "
                               "The embed secret and the password are never returned.",
                   responses={200: MetabaseConnectionSerializer, **errors(401, 403, 404)})
    def get(self, request, **kwargs):
        scope = self.manager(request, kwargs)
        return _private(Response(MetabaseConnectionSerializer(services.describe(scope, request.user)).data))

    @extend_schema(tags=TAGS, summary="Change the Metabase URL, embed secret, dashboards or member-details switch",
                   request=MetabaseConnectionUpdateSerializer,
                   responses={200: MetabaseConnectionSerializer, **errors(400, 401, 403, 404)})
    def patch(self, request, **kwargs):
        scope = self.manager(request, kwargs)
        data = MetabaseConnectionUpdateSerializer(data=request.data)
        data.is_valid(raise_exception=True)
        body = services.update(scope, request.user, data.validated_data)
        return _private(Response(MetabaseConnectionSerializer(body).data))


class AnalyticsLoginView(_Scoped):
    @extend_schema(tags=TAGS, summary="Create the read-only database login (password shown once)", request=None,
                   responses={201: MetabaseCredentialsSerializer, 409: _CONFLICT, 503: _FAILED,
                              **errors(401, 403, 404)})
    def post(self, request, **kwargs):
        scope = self.manager(request, kwargs)
        try:
            body = services.create_login(scope, request.user)
        except services.AnalyticsError as exc:
            return _error(exc)
        return _private(Response(MetabaseCredentialsSerializer(body).data, status=status.HTTP_201_CREATED))

    @extend_schema(tags=TAGS, summary="Revoke (drop) the database login", request=None,
                   responses={204: OpenApiResponse(description="Revoked."), 409: _CONFLICT, 503: _FAILED,
                              **errors(401, 403, 404)})
    def delete(self, request, **kwargs):
        scope = self.manager(request, kwargs)
        try:
            services.revoke_login(scope, request.user)
        except services.AnalyticsError as exc:
            return _error(exc)
        return Response(status=status.HTTP_204_NO_CONTENT)


class AnalyticsLoginRotateView(_Scoped):
    @extend_schema(tags=TAGS, summary="Rotate the login's password (new password shown once)", request=None,
                   responses={200: MetabaseCredentialsSerializer, 409: _CONFLICT, 503: _FAILED,
                              **errors(401, 403, 404)})
    def post(self, request, **kwargs):
        scope = self.manager(request, kwargs)
        try:
            body = services.rotate_login(scope, request.user)
        except services.AnalyticsError as exc:
            return _error(exc)
        return _private(Response(MetabaseCredentialsSerializer(body).data))


class AnalyticsEmbedView(_Scoped):
    @extend_schema(tags=TAGS, summary="A signed, short-lived embed URL for one listed dashboard", request=None,
                   description="view_analytics. The URL expires after ten minutes; the embedding secret never "
                               "leaves the server. Audited.",
                   responses={200: MetabaseEmbedSerializer, 409: _CONFLICT, **errors(401, 403, 404)})
    def get(self, request, dashboard_id, **kwargs):
        scope = self.viewer(request, kwargs)
        try:
            body = services.embed(scope, request.user, dashboard_id)
        except services.AnalyticsError as exc:
            return _error(exc)
        return _private(Response(MetabaseEmbedSerializer(body).data))


def platform(view):
    """The platform variant of a handler class (superadmin only, no module switch)."""
    return type(f"Platform{view.__name__}", (view,), {"platform": True})
