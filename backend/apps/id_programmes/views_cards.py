"""Staff routes for programme cards: list (chips, search), add, edit, delete, bulk
decisions, import, single download/email, photo request and bulk jobs."""
from django.utils.translation import gettext
from django.db.models import Q
from django.http import HttpResponse
from drf_spectacular.types import OpenApiTypes
from drf_spectacular.utils import OpenApiParameter, extend_schema
from rest_framework import status
from rest_framework.exceptions import PermissionDenied, ValidationError
from rest_framework.pagination import PageNumberPagination
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.admin_api.import_sources import SHEET_ERRORS, source_of
from apps.openapi_errors import errors
from apps.card_designs.serializers import CardJobCreateSerializer, CardJobSerializer
from apps.card_designs.serializers_openapi import CreatedIdSerializer, QueuedSerializer, ReasonSerializer

from .serializers_openapi import DecisionResultSerializer, ImportCommitResultSerializer, ImportPreviewResultSerializer

from . import cards, imports
from .access import MANAGE, card_for, programme_for
from .serializers import (DecisionSerializer, IdProgrammeCardCreateSerializer, IdProgrammeCardEditSerializer,
                          IdProgrammeCardSerializer, ImportCommitSerializer, ImportPreviewSerializer)

TAGS = ["ID programmes"]


class _Page(PageNumberPagination):
    page_size = 24


class ProgrammeCardListView(APIView):
    permission_classes = [IsAuthenticated]

    @extend_schema(tags=TAGS, summary="Programme cards (status chip and search)", request=None,
                   parameters=[OpenApiParameter("status", str), OpenApiParameter("search", str)],
                   responses={200: IdProgrammeCardSerializer(many=True), **errors(401, 404)})
    def get(self, request, pk):
        programme = programme_for(request.user, pk)
        rows = programme.cards.all()
        wanted = request.query_params.get("status", "")
        if wanted in ("pending", "approved", "rejected", "revoked"):
            rows = rows.filter(status=wanted)
        search = (request.query_params.get("search") or "").strip()
        if search:
            # Names and emails are encrypted: search matches the ID number and an exact email.
            rows = rows.filter(Q(id_number__icontains=search) | Q(email_digest=cards.email_digest(search)))
        page = _Page()
        items = page.paginate_queryset(rows.order_by("-created_at"), request, view=self)
        return page.get_paginated_response(IdProgrammeCardSerializer(items, many=True,
                                                                     context={"request": request}).data)

    @extend_schema(tags=TAGS, summary="Add a person (they get an emailed invite; nothing links until they accept)",
                   request=IdProgrammeCardCreateSerializer,
                   responses={201: IdProgrammeCardSerializer, **errors(400, 401, 403, 404)})
    def post(self, request, pk):
        from django.db import transaction
        from .invites import send_invites
        programme = programme_for(request.user, pk, MANAGE)
        data = IdProgrammeCardCreateSerializer(data=request.data)
        data.is_valid(raise_exception=True)
        card = cards.add(request.user, programme, **data.validated_data)
        transaction.on_commit(lambda: send_invites([card.pk]), robust=True)
        return Response(IdProgrammeCardSerializer(card, context={"request": request}).data,
                        status=status.HTTP_201_CREATED)


class ProgrammeCardDetailView(APIView):
    permission_classes = [IsAuthenticated]

    @extend_schema(tags=TAGS, summary="Read a programme card", request=None,
                   responses={200: IdProgrammeCardSerializer, **errors(401, 404)})
    def get(self, request, pk):
        return Response(IdProgrammeCardSerializer(card_for(request.user, pk), context={"request": request}).data)

    @extend_schema(tags=TAGS, summary="Change a holder's name or answers", request=IdProgrammeCardEditSerializer,
                   responses={200: IdProgrammeCardSerializer, **errors(400, 401, 403, 404)})
    def patch(self, request, pk):
        card = card_for(request.user, pk, MANAGE)
        data = IdProgrammeCardEditSerializer(data=request.data)
        data.is_valid(raise_exception=True)
        return Response(IdProgrammeCardSerializer(cards.edit(request.user, card, data.validated_data),
                                                  context={"request": request}).data)

    @extend_schema(tags=TAGS, summary="Delete a card (its photo goes too)", request=None,
                   responses={204: None, **errors(401, 403, 404)})
    def delete(self, request, pk):
        cards.delete(request.user, card_for(request.user, pk, MANAGE))
        return Response(status=status.HTTP_204_NO_CONTENT)


class ProgrammeDecisionView(APIView):
    permission_classes = [IsAuthenticated]

    @extend_schema(tags=TAGS, summary="Approve, reject, revoke, reinstate or renew up to 500 cards",
                   request=DecisionSerializer, responses={200: DecisionResultSerializer, **errors(400, 401, 403, 404)})
    def post(self, request, pk):
        programme = programme_for(request.user, pk, MANAGE)
        data = DecisionSerializer(data=request.data)
        data.is_valid(raise_exception=True)
        values = data.validated_data
        ids = values.get("ids") or []
        if values["all"]:
            source = {"approve": "pending", "renew": "approved"}.get(values["action"])
            if source is None:
                raise ValidationError({"all": gettext("“All” works for approve and renew only.")})
            ids = list(programme.cards.filter(status=source).values_list("pk", flat=True)[:500])
        changed = cards.decide(request.user, programme, values["action"], ids, values.get("reason", ""))
        return Response({"changed": len(changed)})


class ProgrammeImportPreviewView(APIView):
    permission_classes = [IsAuthenticated]

    @extend_schema(tags=TAGS, summary="Preview a CSV or public Google Sheet import: headers, 20 rows, mapping, counts",
                   request=ImportPreviewSerializer,
                   responses={200: ImportPreviewResultSerializer, **errors(400, 401, 403, 404), **SHEET_ERRORS})
    def post(self, request, pk):
        programme = programme_for(request.user, pk, MANAGE)
        data = ImportPreviewSerializer(data=request.data)
        data.is_valid(raise_exception=True)
        raw, sheet = imports.read(programme, data.validated_data)
        return Response({**imports.preview(programme, raw), **(sheet.response_fields() if sheet else {})})


class ProgrammeImportView(APIView):
    permission_classes = [IsAuthenticated]

    @extend_schema(tags=TAGS, summary="Import with the confirmed mapping (dry run available)",
                   request=ImportCommitSerializer,
                   responses={200: ImportCommitResultSerializer, **errors(400, 401, 403, 404), **SHEET_ERRORS})
    def post(self, request, pk):
        programme = programme_for(request.user, pk, MANAGE)
        data = ImportCommitSerializer(data=request.data)
        data.is_valid(raise_exception=True)
        values = data.validated_data
        raw, sheet = imports.read(programme, values)
        return Response(imports.commit(request.user, programme, raw, values["mapping"], approve=values["approve"],
                                       dry_run=values["dry_run"], source=source_of(sheet)))


class ProgrammeCardDownloadView(APIView):
    permission_classes = [IsAuthenticated]

    @extend_schema(tags=TAGS, summary="Download one programme card (PDF or PNG side)", request=None,
                   parameters=[OpenApiParameter("format", str), OpenApiParameter("side", str)],
                   responses={(200, "application/pdf"): OpenApiTypes.BINARY, **errors(400, 401, 403, 404)})
    def get(self, request, pk):
        from apps.card_designs.cards import render
        from apps.card_designs.downloads import record_download
        card = card_for(request.user, pk, MANAGE)
        if card.status != "approved":
            raise PermissionDenied(gettext("Only an approved card can be downloaded."))
        fmt, side = request.query_params.get("format", "pdf"), request.query_params.get("side", "front")
        data, content_type, filename = render("programme_card", card, fmt=fmt, side=side)
        record_download(request.user, "programme_card", card, fmt, side)
        response = HttpResponse(data, content_type=content_type)
        response["Content-Disposition"] = f'attachment; filename="{filename}"'
        return response


class ProgrammeCardEmailView(APIView):
    permission_classes = [IsAuthenticated]

    @extend_schema(tags=TAGS, summary="Email one programme card to its holder", request=None,
                   responses={202: QueuedSerializer, **errors(400, 401, 403, 404)})
    def post(self, request, pk):
        from apps.card_designs.email import send_card_email
        if not send_card_email("programme_card", card_for(request.user, pk, MANAGE), actor=request.user, explicit=True):
            raise ValidationError({"detail": gettext("Not sent: emailed recently, over the daily limit, or not approved.")})
        return Response({"queued": True}, status=202)


class ProgrammeCardPhotoRequestView(APIView):
    permission_classes = [IsAuthenticated]

    @extend_schema(tags=TAGS, summary="Ask the holder for a new photo", request=ReasonSerializer,
                   responses={201: CreatedIdSerializer, **errors(400, 401, 403, 404)})
    def post(self, request, pk):
        from apps.card_designs.photos import request_update
        card = card_for(request.user, pk, MANAGE)
        row = request_update(request.user, "programme_card", card, str(request.data.get("reason", ""))[:300])
        return Response({"id": row.pk}, status=201)


class ProgrammeCardJobView(APIView):
    permission_classes = [IsAuthenticated]

    @extend_schema(tags=TAGS, summary="My card jobs for this programme", request=None,
                   responses={200: CardJobSerializer(many=True), **errors(401, 404)})
    def get(self, request, pk):
        from apps.card_designs.jobs import my_jobs
        return Response(my_jobs(request.user, "id_programme", programme_for(request.user, pk).pk))

    @extend_schema(tags=TAGS, summary="Queue a bulk job for approved cards (sheets, per-person PDF, ZIP, email)",
                   request=CardJobCreateSerializer, responses={201: CardJobSerializer, 200: CardJobSerializer, **errors(400, 401, 403, 404)})
    def post(self, request, pk):
        from apps.card_designs.jobs import enqueue
        from apps.card_designs.serializers import CardJobCreateSerializer, CardJobSerializer
        from apps.card_designs.views_jobs import job_params
        programme = programme_for(request.user, pk, MANAGE)
        data = CardJobCreateSerializer(data=request.data)
        data.is_valid(raise_exception=True)
        values = data.validated_data
        rows = programme.cards.filter(status="approved")
        if values.get("card_ids"):
            rows = rows.filter(pk__in=values["card_ids"])
        params = {"explicit": False} if values["kind"] == "email" else job_params(values)
        job, created = enqueue(request.user, programme.makerspace, values["kind"], scope="id_programme",
                               scope_id=programme.pk, targets=list(rows.values_list("pk", flat=True)), params=params,
                               revision=programme.card_designs.values_list("published_revision", flat=True).first())
        return Response(CardJobSerializer(job).data, status=201 if created else 200)
