"""Card and certificate template routes (SPEC section 10): gallery, save from a design, edit, export/import, apply."""
from drf_spectacular.utils import OpenApiParameter, extend_schema
from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.exceptions import NotFound
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.openapi_errors import errors
from apps.tenant_migration.gate_runtime import assert_write_allowed

from . import templates, templates_files
from .authority import acted_for, design_for, require_edit
from .serializers import CardDesignSerializer
from .serializers_templates import (TemplateApplySerializer, TemplateAppliedSerializer, TemplateCreateSerializer,
                                    TemplateDetailSerializer, TemplateFileSerializer, TemplateImportSerializer,
                                    TemplateRowSerializer, TemplateUpdateSerializer)
from .template_access import design_in_space, row_for, space_for

TAGS = ["Card templates"]


class CardTemplateCollectionView(APIView):
    permission_classes = [IsAuthenticated]

    @extend_schema(tags=TAGS, summary="List built-in and saved templates (no documents)",
                   parameters=[OpenApiParameter("kind", str, required=False, enum=["card", "certificate"]),
                               OpenApiParameter("stock", str, required=False),
                               OpenApiParameter("source", str, required=False, enum=["builtin", "space"])],
                   request=None, responses={200: TemplateRowSerializer(many=True), **errors(401, 403, 404)})
    def get(self, request, makerspace_id):
        space = space_for(request.user, makerspace_id)
        kind, stock, source = (request.query_params.get(key) or None for key in ("kind", "stock", "source"))
        rows = [] if source == "space" else [row for row in templates.builtin_rows(kind) if not stock or row["stock"] == stock]
        if source != "builtin":
            rows += templates.space_rows(space, kind, stock)
        return Response(rows)

    @extend_schema(tags=TAGS, summary="Save a design (or a certificate document) as a space template",
                   description="A card design needs edit rights on it; a certificate is sent as `document`. 409 `extra_quota_reached` when the `card_templates` "
                               "limit is set and used up.",
                   request=TemplateCreateSerializer, responses={201: TemplateDetailSerializer, **errors(400, 401, 403, 404, 409)})
    def post(self, request, makerspace_id):
        space = space_for(request.user, makerspace_id)
        assert_write_allowed(space.pk)
        data = TemplateCreateSerializer(data=request.data)
        data.is_valid(raise_exception=True)
        if "document" in data.validated_data:  # a certificate design (not a CardDesign row)
            row = templates.create_from_document(request.user, space, data.validated_data["document"],
                                                 data.validated_data["name"], data.validated_data["description"])
            return Response(templates.row_dict(row, document=True), status=status.HTTP_201_CREATED)
        design = design_in_space(request.user, space, data.validated_data["design_id"])
        row = templates.create_from_design(request.user, space, design, data.validated_data["name"],
                                           data.validated_data["description"])
        return Response(templates.row_dict(row, document=True), status=status.HTTP_201_CREATED)


class CardTemplateBuiltinView(APIView):
    permission_classes = [IsAuthenticated]

    @extend_schema(tags=TAGS, summary="Read a built-in template (card or certificate) with its document",
                   description="`key` is a built-in look such as `studio_lanyard` or `cert_laurel`; `theme` is light or dark. "
                               "The document is built in code and carries no space data.",
                   request=None, responses={200: TemplateDetailSerializer, **errors(401, 403, 404)})
    def get(self, request, makerspace_id, key, theme):
        space_for(request.user, makerspace_id)
        if theme not in ("light", "dark"):
            raise NotFound()
        return Response(templates.builtin_document(key, theme))


class CardTemplateImportView(APIView):
    permission_classes = [IsAuthenticated]

    @extend_schema(tags=TAGS, summary="Import a template file into this space",
                   description="Images in the file are re-encoded and stored privately in this space; a file from a "
                               "newer format version is refused.",
                   request=TemplateImportSerializer, responses={201: TemplateDetailSerializer, **errors(400, 401, 403, 404, 409)})
    def post(self, request, makerspace_id):
        space = space_for(request.user, makerspace_id)
        assert_write_allowed(space.pk)
        data = TemplateImportSerializer(data=request.data)
        data.is_valid(raise_exception=True)
        row = templates_files.import_file(request.user, space, data.validated_data["file"])
        return Response(templates.row_dict(row, document=True), status=status.HTTP_201_CREATED)


class CardTemplateDetailView(APIView):
    permission_classes = [IsAuthenticated]

    @extend_schema(tags=TAGS, summary="Read a saved template with its document", request=None,
                   responses={200: TemplateDetailSerializer, **errors(401, 403, 404)})
    def get(self, request, pk):
        _space, row = row_for(request.user, pk)
        return Response(templates.row_dict(row, document=True))

    @extend_schema(tags=TAGS, summary="Rename a saved template or replace its document",
                   request=TemplateUpdateSerializer, responses={200: TemplateDetailSerializer, **errors(400, 401, 403, 404)})
    def patch(self, request, pk):
        space, row = row_for(request.user, pk)
        assert_write_allowed(space.pk)
        data = TemplateUpdateSerializer(data=request.data, partial=True)
        data.is_valid(raise_exception=True)
        row = templates.update(request.user, space, row, **data.validated_data)
        return Response(templates.row_dict(row, document=True))

    @extend_schema(tags=TAGS, summary="Delete a saved template", request=None, responses={204: None, **errors(401, 403, 404)})
    def delete(self, request, pk):
        space, row = row_for(request.user, pk)
        assert_write_allowed(space.pk)
        templates.delete(request.user, space, row)
        return Response(status=status.HTTP_204_NO_CONTENT)


class CardTemplateDuplicateView(APIView):
    permission_classes = [IsAuthenticated]

    @extend_schema(tags=TAGS, summary="Duplicate a saved template", request=None,
                   responses={201: TemplateDetailSerializer, **errors(401, 403, 404, 409)})
    def post(self, request, pk):
        space, row = row_for(request.user, pk)
        assert_write_allowed(space.pk)
        return Response(templates.row_dict(templates.duplicate(request.user, space, row), document=True),
                        status=status.HTTP_201_CREATED)


class CardTemplateExportView(APIView):
    permission_classes = [IsAuthenticated]

    @extend_schema(tags=TAGS, summary="Export a saved template as a JSON file, images included", request=None,
                   responses={200: TemplateFileSerializer, **errors(400, 401, 403, 404)})
    def get(self, request, pk):
        space, row = row_for(request.user, pk)
        response = Response(templates_files.export_file(space, row))
        response["Content-Disposition"] = f'attachment; filename="template-{row.pk}.json"'
        return response


class CardDesignApplyTemplateView(APIView):
    permission_classes = [IsAuthenticated]

    @extend_schema(tags=TAGS, summary="Apply a template to a design, keeping its data-field bindings",
                   description="Saves a new revision of the design (compare-and-swap on `expected_revision`). Data fields "
                               "the design bound that the template lacks are appended and listed in `unplaced_fields`.",
                   request=TemplateApplySerializer, responses={200: TemplateAppliedSerializer, **errors(400, 401, 403, 404, 409)})
    def post(self, request, pk):
        design = require_edit(request.user, design_for(request.user, pk))
        assert_write_allowed(design.makerspace_id)
        data = TemplateApplySerializer(data=request.data)
        data.is_valid(raise_exception=True)
        values = data.validated_data
        saved, unplaced = templates.apply(request.user, design.makerspace, design, values["template"],
                                          expected_revision=values["expected_revision"], keep_fields=values["keep_fields"],
                                          theme=values["theme"], acted_for=acted_for(request.user, design))
        saved.refresh_from_db()
        return Response({"design": CardDesignSerializer(saved, context={"request": request}).data,
                         "unplaced_fields": unplaced})
