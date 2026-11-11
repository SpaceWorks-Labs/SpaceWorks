"""Privacy and terms: the public read, the operator's editor and a space's own override (parity E-B8, A13)."""

from django.db import transaction
from django.http import Http404
from django.shortcuts import get_object_or_404
from django.utils.translation import gettext, gettext_lazy
from drf_spectacular.utils import OpenApiParameter, extend_schema
from rest_framework import serializers
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.accounts import rbac
from apps.admin_api.permissions import IsActiveStaff, IsActiveSuperAdmin, require_action
from apps.apiclients.throttling import ClientTierRateThrottle
from apps.audit import services as audit
from apps.makerspaces.lookup import get_public_makerspace
from apps.makerspaces.servability import servable_queryset
from apps.openapi_errors import errors

from . import legal_pages

SLUG_ERROR = gettext_lazy("Unknown page.")


class LegalPageSerializer(serializers.Serializer):
    slug = serializers.ChoiceField(choices=legal_pages.SLUGS)
    markdown = serializers.CharField(help_text="Markdown. Render without raw HTML.")
    source = serializers.ChoiceField(choices=("space", "platform", "default"))
    language = serializers.CharField(allow_blank=True)
    updated_at = serializers.DateTimeField(allow_null=True)


class LegalPageWriteSerializer(serializers.Serializer):
    markdown = serializers.CharField(allow_blank=True, max_length=legal_pages.MAX_LENGTH, trim_whitespace=False)
    language = serializers.RegexField(r"^[a-z]{2,3}(-[A-Za-z0-9]{2,8})?$|^$", required=False, allow_blank=True,
                                      default="", max_length=16)


def _slug(value):
    if value not in legal_pages.SLUGS:
        raise Http404(SLUG_ERROR)
    return value


class PublicLegalPageView(APIView):
    """GET /api/v1/discover/legal/<privacy|terms>/ — anonymous; `?space=<slug>` adds that space's own text."""

    permission_classes = [AllowAny]
    authentication_classes = []
    throttle_classes = [ClientTierRateThrottle]
    throttle_scope = "public_read"

    @extend_schema(tags=["Public websites"], auth=[], parameters=[OpenApiParameter(
        "space", str, description="Space slug or code; when that space wrote its own page, that text is returned.")],
        responses={200: LegalPageSerializer, **errors(404, 429)})
    def get(self, request, page):
        slug = _slug(page)
        raw = request.query_params.get("space", "")
        space = get_public_makerspace(raw) if raw else None
        return Response(LegalPageSerializer(legal_pages.resolve(slug, makerspace=space)).data,
                        headers={"Cache-Control": "public, max-age=300"})


class PlatformLegalPageView(APIView):
    """GET / PUT / DELETE admin/platform/legal-pages/<slug> — the operator's text (superadmin only)."""

    permission_classes = [IsActiveSuperAdmin]
    http_method_names = ["get", "put", "delete", "head", "options"]

    @extend_schema(tags=["Platform"], summary="Read a privacy / terms page as the operator edits it",
                   parameters=[OpenApiParameter("language", str)],
                   responses={200: LegalPageSerializer, **errors(401, 403, 404)})
    def get(self, request, slug):
        data = legal_pages.resolve(_slug(slug), language=request.query_params.get("language") or None)
        return Response(LegalPageSerializer(data).data)

    @extend_schema(tags=["Platform"], summary="Replace a privacy / terms page", request=LegalPageWriteSerializer,
                   responses={200: LegalPageSerializer, **errors(400, 401, 403, 404)})
    def put(self, request, slug):
        slug = _slug(slug)
        body = LegalPageWriteSerializer(data=request.data)
        body.is_valid(raise_exception=True)
        language, text = body.validated_data["language"], legal_pages.clean_markdown(body.validated_data["markdown"])
        if not text:
            raise serializers.ValidationError({"markdown": gettext("Write the page, or delete it to use the default.")})
        with transaction.atomic():
            row = legal_pages.set_platform_page(slug, language, text)
            audit.record(request.user, "platform.legal_page_updated", target=None,
                         meta={"page": slug, "language": language, "action": "set", "length": len(text)})
        return Response(LegalPageSerializer(legal_pages.resolve(slug, language=row.language or None)).data)

    @extend_schema(tags=["Platform"], summary="Return a privacy / terms page to the shipped default",
                   parameters=[OpenApiParameter("language", str)], responses={204: None, **errors(401, 403, 404)})
    def delete(self, request, slug):
        slug = _slug(slug)
        language = request.query_params.get("language", "")
        with transaction.atomic():
            removed = legal_pages.reset_platform_page(slug, language)
            audit.record(request.user, "platform.legal_page_updated", target=None,
                         meta={"page": slug, "language": language, "action": "reset", "length": 0})
        return Response(status=204 if removed else 404)


class SpaceLegalPageView(APIView):
    """GET / PUT admin/makerspace/<id>/legal-pages/<slug> — a space's own override (MANAGE_MAKERSPACE)."""

    permission_classes = [IsActiveStaff]
    http_method_names = ["get", "put", "head", "options"]

    def _space(self, request, makerspace_id):
        require_action(request.user, rbac.Action.MANAGE_MAKERSPACE, makerspace_id)
        return get_object_or_404(servable_queryset(), pk=makerspace_id)

    @extend_schema(tags=["Makerspaces"], summary="Read the page a space's visitors see",
                   responses={200: LegalPageSerializer, **errors(401, 403, 404)})
    def get(self, request, makerspace_id, slug):
        space = self._space(request, makerspace_id)
        return Response(LegalPageSerializer(legal_pages.resolve(_slug(slug), makerspace=space)).data)

    @extend_schema(tags=["Makerspaces"], summary="Set (or clear, when blank) a space's own privacy / terms text",
                   request=LegalPageWriteSerializer, responses={200: LegalPageSerializer, **errors(400, 401, 403, 404)})
    def put(self, request, makerspace_id, slug):
        slug = _slug(slug)
        space = self._space(request, makerspace_id)
        if not legal_pages.space_pages_enabled(space):
            raise Http404(gettext("Own privacy and terms pages are switched off for this space."))
        body = LegalPageWriteSerializer(data=request.data)
        body.is_valid(raise_exception=True)
        with transaction.atomic():
            text = legal_pages.set_space_override(space, slug, body.validated_data["markdown"])
            audit.record(request.user, "makerspace.legal_page_updated", makerspace=space, target=space,
                         meta={"page": slug, "action": "set" if text else "clear", "length": len(text)})
        return Response(LegalPageSerializer(legal_pages.resolve(slug, makerspace=space)).data)
