"""Decision 263: Grafana routes, one set per space (``admin/makerspaces/<id>/grafana/...``) and
one for the platform (``admin/platform/grafana/...``), sharing every handler and the access
rules of the Metabase routes: viewers need view_analytics in the space, managing is the
space's Space Manager or the superadmin, the platform set is the superadmin's alone, and a
space with the analytics module off answers the typed module-off body."""

from django.http import HttpResponse
from drf_spectacular.types import OpenApiTypes
from drf_spectacular.utils import OpenApiParameter, OpenApiResponse, extend_schema
from rest_framework import status
from rest_framework.response import Response

from apps.openapi_errors import errors

from . import access, grafana_live, grafana_services
from .api import _Scoped, _error, _private
from .grafana_serializers import (
    GrafanaBundleSerializer, GrafanaConnectionSerializer, GrafanaConnectionUpdateSerializer, GrafanaEmbedSerializer,
    GrafanaSummarySerializer, GrafanaTestSerializer, GrafanaTokenSerializer,
)
from .serializers import MetabaseErrorSerializer
from .services import AnalyticsError

TAGS = ["Analytics"]
_CONFLICT = OpenApiResponse(MetabaseErrorSerializer, description=(
    "grafana_not_enabled, grafana_not_configured, grafana_token_missing, grafana_dashboard_unknown "
    "or grafana_unreachable."))


class GrafanaSummaryView(_Scoped):
    @extend_schema(tags=TAGS, summary="Grafana dashboards available to the viewer", request=None,
                   description="view_analytics in the space (or the superadmin for the platform). Never returns "
                               "a token or a public dashboard access token.",
                   responses={200: GrafanaSummarySerializer, **errors(401, 403, 404)})
    def get(self, request, **kwargs):
        scope = self.viewer(request, kwargs)
        body = {**grafana_services.summary(scope), "can_manage": access.can_manage(request.user, scope)}
        return Response(GrafanaSummarySerializer(body).data)


class GrafanaConnectionView(_Scoped):
    @extend_schema(tags=TAGS, summary="Read the Grafana connection", request=None,
                   description="Space Manager of the space or the superadmin. Audited as a credentials view. "
                               "The service-account token is never returned.",
                   responses={200: GrafanaConnectionSerializer, **errors(401, 403, 404)})
    def get(self, request, **kwargs):
        scope = self.manager(request, kwargs)
        return _private(Response(GrafanaConnectionSerializer(grafana_services.describe(scope, request.user)).data))

    @extend_schema(tags=TAGS, summary="Change the provider, Grafana URL, organization or dashboards",
                   request=GrafanaConnectionUpdateSerializer,
                   responses={200: GrafanaConnectionSerializer, **errors(400, 401, 403, 404)})
    def patch(self, request, **kwargs):
        scope = self.manager(request, kwargs)
        data = GrafanaConnectionUpdateSerializer(data=request.data)
        data.is_valid(raise_exception=True)
        body = grafana_services.update(scope, request.user, data.validated_data)
        return _private(Response(GrafanaConnectionSerializer(body).data))


class GrafanaTokenView(_Scoped):
    @extend_schema(tags=TAGS, summary="Save or rotate the Grafana service-account token", request=GrafanaTokenSerializer,
                   description="Encrypted at rest and never returned. Audited as created or rotated.",
                   responses={200: GrafanaConnectionSerializer, **errors(400, 401, 403, 404)})
    def post(self, request, **kwargs):
        scope = self.manager(request, kwargs)
        data = GrafanaTokenSerializer(data=request.data)
        data.is_valid(raise_exception=True)
        body = grafana_services.set_token(scope, request.user, data.validated_data["token"])
        return _private(Response(GrafanaConnectionSerializer(body).data))

    @extend_schema(tags=TAGS, summary="Revoke (forget) the Grafana token", request=None,
                   responses={204: OpenApiResponse(description="Revoked."), 409: _CONFLICT, **errors(401, 403, 404)})
    def delete(self, request, **kwargs):
        scope = self.manager(request, kwargs)
        try:
            grafana_services.revoke_token(scope, request.user)
        except AnalyticsError as exc:
            return _error(exc)
        return Response(status=status.HTTP_204_NO_CONTENT)


class GrafanaTestView(_Scoped):
    @extend_schema(tags=TAGS, summary="Test the saved Grafana connection", request=None,
                   description="Calls Grafana's /api/health and /api/search with the saved token. A space's "
                               "Grafana must be on a public address unless the deployment allows private ones.",
                   responses={200: GrafanaTestSerializer, 409: _CONFLICT, **errors(401, 403, 404)})
    def post(self, request, **kwargs):
        scope = self.manager(request, kwargs)
        try:
            body = grafana_live.check_connection(scope, request.user)
        except AnalyticsError as exc:
            return _error(exc)
        return _private(Response(GrafanaTestSerializer(body).data))


class GrafanaBundleView(_Scoped):
    @extend_schema(tags=TAGS, summary="Download the Grafana data source and starter dashboards", request=None,
                   description="JSON by default; ?archive=zip returns Grafana provisioning files. The password "
                               "is always a placeholder. Only this scope's login and curated views are used.",
                   parameters=[OpenApiParameter("archive", str, enum=["zip"], required=False)],
                   responses={(200, "application/json"): GrafanaBundleSerializer,
                              (200, "application/zip"): OpenApiTypes.BINARY, **errors(401, 403, 404)})
    def get(self, request, **kwargs):
        scope = self.manager(request, kwargs)
        archive = request.query_params.get("archive") == "zip"
        body = grafana_services.bundle(scope, request.user, archive=archive)
        name = f"spaceworks-grafana-{'platform' if scope.platform else f'space-{scope.makerspace.pk}'}"
        if archive:
            response = HttpResponse(body, content_type="application/zip")
            response["Content-Disposition"] = f'attachment; filename="{name}.zip"'
            return _private(response)
        response = Response(GrafanaBundleSerializer(body).data)
        response["Content-Disposition"] = f'attachment; filename="{name}.json"'
        return _private(response)


class GrafanaEmbedView(_Scoped):
    @extend_schema(tags=TAGS, summary="The public (shared) dashboard URL of one listed Grafana dashboard",
                   request=None, responses={200: GrafanaEmbedSerializer, 409: _CONFLICT, **errors(401, 403, 404)})
    def get(self, request, uid, **kwargs):
        scope = self.viewer(request, kwargs)
        try:
            body = grafana_live.embed(scope, request.user, uid)
        except AnalyticsError as exc:
            return _error(exc)
        return _private(Response(GrafanaEmbedSerializer(body).data))


class GrafanaRenderView(_Scoped):
    @extend_schema(tags=TAGS, summary="A PNG of one listed Grafana dashboard, rendered with the saved token",
                   request=None, parameters=[
                       OpenApiParameter("width", int, required=False), OpenApiParameter("height", int, required=False),
                       OpenApiParameter("theme", str, enum=["light", "dark"], required=False)],
                   responses={(200, "image/png"): OpenApiTypes.BINARY, 409: _CONFLICT, **errors(401, 403, 404)})
    def get(self, request, uid, **kwargs):
        scope = self.viewer(request, kwargs)
        width = _bounded(request.query_params.get("width"), 1600, 320, 3840)
        height = _bounded(request.query_params.get("height"), 900, 240, 4320)
        theme = "dark" if request.query_params.get("theme") == "dark" else "light"
        try:
            png = grafana_live.render(scope, request.user, uid, width=width, height=height, theme=theme)
        except AnalyticsError as exc:
            return _error(exc)
        return _private(HttpResponse(png, content_type="image/png"))


def _bounded(raw, default, low, high):
    try:
        return min(max(int(raw), low), high)
    except (TypeError, ValueError):
        return default


def platform(view):
    """The platform variant of a handler class (superadmin only, no module switch)."""
    return type(f"Platform{view.__name__}", (view,), {"platform": True, "__module__": __name__})
