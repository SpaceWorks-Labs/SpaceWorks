"""Staff card-design endpoints: list/create per space, read/save one design (CAS)."""
from django.utils.translation import gettext
from django.shortcuts import get_object_or_404
from drf_spectacular.utils import extend_schema
from rest_framework import status
from rest_framework.exceptions import ValidationError
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.openapi_errors import errors

from . import designs, resolution
from .authority import acted_for, design_for, require_edit, space_for
from .default_templates import LABELS, THEMES, build
from .models import CardDesign
from .serializers import (CardDesignCreateSerializer, CardDesignSaveSerializer, CardDesignSerializer,
                          CardTemplateSerializer)

TAGS = ["Card designs"]


class CardTemplateListView(APIView):
    permission_classes = [IsAuthenticated]

    @extend_schema(tags=TAGS, summary="List the six card templates, light and dark, for this design's domain", request=None,
                   responses={200: CardTemplateSerializer(many=True), **errors(400, 401, 403, 404)})
    def get(self, request, pk):
        domain = require_edit(request.user, design_for(request.user, pk)).domain
        return Response([{"key": key, "label": label, "theme": theme, "document": build(key, domain, theme)}
                         for theme in THEMES for key, label in LABELS.items()])


class SpaceCardDesignListView(APIView):
    permission_classes = [IsAuthenticated]

    @extend_schema(tags=TAGS, summary="List member-card designs (space default, plan and title overrides)",
                   request=None, responses={200: CardDesignSerializer(many=True), **errors(400, 401, 403, 404)})
    def get(self, request, makerspace_id):
        space = space_for(request.user, makerspace_id)
        resolution.get_or_create(space, "member_cards", actor=request.user)
        rows = CardDesign.objects.filter(makerspace=space, domain="member_cards").select_related("plan", "title")
        return Response(CardDesignSerializer(rows, many=True, context={"request": request}).data)

    @extend_schema(tags=TAGS, summary="Create a per-plan or per-title member-card design",
                   request=CardDesignCreateSerializer,
                   responses={201: CardDesignSerializer, 200: CardDesignSerializer, **errors(400, 401, 403, 404)})
    def post(self, request, makerspace_id):
        space = space_for(request.user, makerspace_id)
        data = CardDesignCreateSerializer(data=request.data)
        data.is_valid(raise_exception=True)
        values = data.validated_data
        if values["domain"] != "member_cards" or bool(values.get("plan_id")) == bool(values.get("title_id")):
            raise ValidationError({"detail": gettext("Choose exactly one plan or one title for an override.")})
        from apps.makerspaces.models import MembershipPlan, MembershipTitle
        target = {}
        if values.get("plan_id"):
            target["plan"] = get_object_or_404(MembershipPlan, pk=values["plan_id"], makerspace=space)
        else:
            target["title"] = get_object_or_404(MembershipTitle, pk=values["title_id"], makerspace=space)
        row, created = resolution.get_or_create(space, "member_cards", actor=request.user,
                                                template=values.get("template"), theme=values["theme"],
                                                **target)
        return Response(CardDesignSerializer(row, context={"request": request}).data,
                        status=status.HTTP_201_CREATED if created else status.HTTP_200_OK)


class CardDesignDetailView(APIView):
    permission_classes = [IsAuthenticated]

    @extend_schema(tags=TAGS, summary="Read a card design", request=None,
                   responses={200: CardDesignSerializer, **errors(401, 403, 404)})
    def get(self, request, pk):
        return Response(CardDesignSerializer(design_for(request.user, pk), context={"request": request}).data)

    @extend_schema(tags=TAGS, summary="Save a card design draft (compare-and-swap on revision)",
                   description="Holders keep the published design until a publish. Audited at most once per "
                               "10 minutes of autosave.",
                   request=CardDesignSaveSerializer, responses={200: CardDesignSerializer, **errors(400, 401, 403, 404, 409)})
    def put(self, request, pk):
        design = require_edit(request.user, design_for(request.user, pk))
        data = CardDesignSaveSerializer(data=request.data)
        data.is_valid(raise_exception=True)
        if "name" in data.validated_data:
            CardDesign.objects.filter(pk=design.pk).update(name=data.validated_data["name"])
        design = designs.save(request.user, design, data.validated_data["document"],
                              expected_revision=data.validated_data["revision"],
                              acted_for=acted_for(request.user, design))
        design.refresh_from_db()
        return Response(CardDesignSerializer(design, context={"request": request}).data)

    @extend_schema(tags=TAGS, summary="Delete a plan or title override (the space default stays)", request=None,
                   responses={204: None, **errors(400, 401, 403, 404)})
    def delete(self, request, pk):
        design = require_edit(request.user, design_for(request.user, pk))
        if not (design.plan_id or design.title_id or design.ticket_type_id or
                (design.event_id and design.domain in ("event_card", "event_ticket"))):
            raise ValidationError({"detail": gettext("The default design cannot be deleted; reset it instead.")})
        from apps.audit import services as audit
        audit.record(request.user, "card_design.deleted", makerspace=design.makerspace, target=design,
                     meta={"design_id": design.pk, "domain": design.domain})
        design.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)
