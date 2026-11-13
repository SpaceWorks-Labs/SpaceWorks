"""Gated image streams; a retained reference alone never authorizes public bytes."""

from django.utils.translation import gettext
from django.shortcuts import get_object_or_404
from drf_spectacular.utils import OpenApiResponse, extend_schema
from rest_framework.parsers import MultiPartParser
from rest_framework.response import Response
from rest_framework.exceptions import NotFound
from apps.evidence.storage import StorageUnavailable
from .public_page_editor_views import PageEditorBase, ERRORS, data
from .public_profile_views import PublicProfileBase
from .public_page_serializers import AssetUploadInput, AssetUploadResult, VersionInput, EditorState
from . import public_page_assets as assets
from .public_page_services import read_state
from .public_page_access import public_page
from .website_serving import private_image_response
from .website_uploads import WebsiteUploadLimit
from .public_page_errors import PagePayloadTooLarge
from rest_framework.exceptions import ParseError


class PageUploadLimit(WebsiteUploadLimit):
    def handle_raw_input(self, *args, **kwargs):
        try:
            return super().handle_raw_input(*args, **kwargs)
        except ParseError as exc:
            raise PagePayloadTooLarge() from exc

    def receive_data_chunk(self, *args, **kwargs):
        try:
            return super().receive_data_chunk(*args, **kwargs)
        except ParseError as exc:
            raise PagePayloadTooLarge() from exc


def image(asset, kind, owner_id):
    if not assets.owns(asset, kind, owner_id):
        raise NotFound()
    return private_image_response(asset.object_key)


class PageAssetsView(PageEditorBase):
    parser_classes = [MultiPartParser]

    def initialize_request(self, request, *args, **kwargs):
        request.upload_handlers.insert(0, PageUploadLimit(request))
        return super().initialize_request(request, *args, **kwargs)

    @extend_schema(tags=["Page editor"], request=AssetUploadInput, responses={201: AssetUploadResult, **ERRORS})
    def post(self, request, pk, kind="makerspace"):
        try:
            result = assets.upload(kind, pk, actor=request.user, **data(AssetUploadInput, request))
        except StorageUnavailable:
            return Response({"detail": gettext("Image storage is unavailable.")}, status=503)
        return Response(AssetUploadResult(result).data, status=201)


class PageAssetDetailView(PageEditorBase):
    @extend_schema(tags=["Page editor"], responses={200: OpenApiResponse(bytes, description="Private WebP image; no-store."), **ERRORS})
    def get(self, request, pk, asset_id, kind="makerspace"):
        # A read takes no locks or tenant fence; storage is read with no transaction open.
        typed, owner, _, page = read_state(kind, pk, request.user)
        asset = get_object_or_404(typed.asset, pk=asset_id, page=page)
        if not assets.owns(asset, kind, owner.pk):
            raise NotFound()
        return private_image_response(asset.object_key)

    @extend_schema(tags=["Page editor"], request=VersionInput, responses={200: EditorState, **ERRORS})
    def delete(self, request, pk, asset_id, kind="makerspace"):
        return Response(EditorState(assets.delete(kind, pk, asset_id, actor=request.user, **data(VersionInput, request))).data)


class PublicPageAssetView(PublicProfileBase):
    @extend_schema(tags=["Public pages"], auth=[], responses={
        200: OpenApiResponse(bytes, description="Currently visible private WebP image; no-store."), **ERRORS})
    def get(self, request, asset_id, makerspace_slug=None, slug=None, kind="makerspace"):
        self.cache_headers()
        if kind == "makerspace":
            from .models import Makerspace
            owner = get_object_or_404(Makerspace, slug=makerspace_slug)
        else:
            from apps.organizations.models import Organization
            owner = get_object_or_404(Organization, slug=slug)
        page = public_page(kind, owner, request)
        if asset_id not in assets.public_asset_ids(page.published_revision):
            raise NotFound()
        asset = get_object_or_404(page.assets, pk=asset_id)
        return image(asset, kind, owner.pk)
