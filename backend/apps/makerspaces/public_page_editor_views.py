"""Thin authenticated adapters over owner-locked page services."""

from django.db import transaction
from drf_spectacular.utils import OpenApiParameter, OpenApiResponse, extend_schema
from rest_framework.response import Response
from rest_framework.views import APIView
from apps.admin_api.permissions import IsActiveStaff
from apps.apiclients.throttling import ClientTierRateThrottle
from . import public_page_services as services
from .public_page_serializers import (
    EditorState, SaveInput, PublishInput, VersionInput, HandleInput, HandleAvailability, RevisionList,
    PreviewProjection,
)
from .public_profile_handles import normalize_handle, name_available

ERRORS = {code: OpenApiResponse(description=message) for code, message in (
    (400, "Invalid document or field."), (401, "Sign in required."), (403, "Owner authority/origin refused."),
    (404, "Unknown or out-of-scope owner."), (409, "stale_version, handle_unavailable, handle_cooldown or asset_referenced."),
    (413, "Document or upload too large."), (429, "Rate limit exceeded."), (503, "Storage unavailable."))}


def data(serializer, request):
    value = serializer(data=request.data)
    value.is_valid(raise_exception=True)
    return value.validated_data


class PageEditorBase(APIView):
    permission_classes = [IsActiveStaff]
    throttle_classes = [ClientTierRateThrottle]
    throttle_scope = "public_read"

    def finalize_response(self, request, response, *args, **kwargs):
        response = super().finalize_response(request, response, *args, **kwargs)
        response["Cache-Control"] = "private, no-store"
        from django.utils.cache import patch_vary_headers
        patch_vary_headers(response, ("Authorization", "Cookie", "Origin"))
        return response


class PageEditorView(PageEditorBase):
    @extend_schema(tags=["Page editor"], responses={200: EditorState, **ERRORS})
    def get(self, request, pk, kind="makerspace"):
        return Response(EditorState(services.read_editor(kind, pk, actor=request.user)).data)

    @extend_schema(tags=["Page editor"], request=SaveInput, responses={200: EditorState, **ERRORS})
    def put(self, request, pk, kind="makerspace"):
        return Response(EditorState(services.save(kind, pk, actor=request.user, request=request,
                                                  **data(SaveInput, request))).data)


class PagePublishView(PageEditorBase):
    @extend_schema(tags=["Page editor"], request=PublishInput, responses={200: EditorState, **ERRORS})
    def post(self, request, pk, kind="makerspace"):
        return Response(EditorState(services.publish(kind, pk, actor=request.user, **data(PublishInput, request))).data)


class PageUnpublishView(PageEditorBase):
    @extend_schema(tags=["Page editor"], request=VersionInput, responses={200: EditorState, **ERRORS})
    def post(self, request, pk, kind="makerspace"):
        return Response(EditorState(services.unpublish(kind, pk, actor=request.user, **data(VersionInput, request))).data)


class PageHandleView(PageEditorBase):
    @extend_schema(tags=["Page editor"], request=HandleInput, responses={200: EditorState, **ERRORS})
    def put(self, request, pk, kind="makerspace"):
        return Response(EditorState(services.change_handle(kind, pk, actor=request.user, **data(HandleInput, request))).data)

    @extend_schema(tags=["Page editor"], request=VersionInput, responses={200: EditorState, **ERRORS})
    def delete(self, request, pk, kind="makerspace"):
        return Response(EditorState(services.change_handle(kind, pk, actor=request.user, release=True,
                                                           **data(VersionInput, request))).data)


class PageHandleAvailabilityView(PageEditorBase):
    @extend_schema(tags=["Page editor"], parameters=[OpenApiParameter("handle", str, required=True)],
                   responses={200: HandleAvailability, **ERRORS})
    @transaction.atomic
    def get(self, request, pk, kind="makerspace"):
        services.lock_state(kind, pk, request.user)
        handle = normalize_handle(request.query_params.get("handle", ""))
        return Response({"handle": handle, "available": name_available(handle)})


class PagePreviewView(PageEditorBase):
    @extend_schema(tags=["Page editor"], request=SaveInput, responses={200: PreviewProjection, **ERRORS})
    def post(self, request, pk, kind="makerspace"):
        return Response(PreviewProjection(services.preview(kind, pk, actor=request.user, request=request,
                                                           **data(SaveInput, request))).data)


class PageRevisionsView(PageEditorBase):
    @extend_schema(tags=["Page editor"], parameters=[OpenApiParameter("page", int)], responses={200: RevisionList, **ERRORS})
    @transaction.atomic
    def get(self, request, pk, kind="makerspace"):
        from .public_page_pagination import PagePagination
        _, _, _, page = services.lock_state(kind, pk, request.user)
        paginator = PagePagination()
        rows = page.revisions.select_related("created_by").order_by("-created_at", "-id") if page else []
        selected = paginator.paginate_queryset(rows, request, view=self)
        return paginator.get_paginated_response([{"id": row.pk, "created_at": row.created_at,
            "created_by_display": row.created_by.display_name if row.created_by else None,
            "summary": {"section_types": [section["type"] for section in row.document["sections"]]}}
            for row in selected])
