"""Title cards list and card number schemes (O-B4). Staff routes under /api/v1/admin/makerspaces/<id>/."""
from django.db import transaction
from django.shortcuts import get_object_or_404
from drf_spectacular.utils import extend_schema
from rest_framework import serializers
from rest_framework.exceptions import NotFound
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.audit import services as audit
from apps.makerspaces.platform import feature_enabled
from apps.openapi_errors import errors

from . import numbering, title_cards
from .authority import space_for
from .models_numbering import CardNumberScheme
from .switches import CARD_NUMBERING

TAGS = ["Card designs"]


class TitleCardSerializer(serializers.Serializer):
    title_id = serializers.IntegerField()
    title = serializers.CharField()
    design_id = serializers.IntegerField(allow_null=True)
    status = serializers.ChoiceField(choices=("inherits", "draft", "published", "changes"))
    number_pattern = serializers.CharField(allow_blank=True)
    live_cards = serializers.IntegerField()


class NumberSchemeSerializer(serializers.Serializer):
    title_id = serializers.IntegerField(allow_null=True)
    prefix = serializers.CharField(allow_blank=True)
    pattern = serializers.CharField(allow_blank=True)
    draft_prefix = serializers.CharField(allow_blank=True)
    draft_pattern = serializers.CharField(allow_blank=True)
    pending = serializers.BooleanField(help_text="A draft that goes live when its design is published.")
    published_at = serializers.DateTimeField(allow_null=True)
    preview = serializers.ListField(child=serializers.CharField(), help_text="Three sample numbers of the draft.")


class NumberSchemeListSerializer(serializers.Serializer):
    default = NumberSchemeSerializer()
    titles = NumberSchemeSerializer(many=True)


class NumberSchemeWriteSerializer(serializers.Serializer):
    prefix = serializers.CharField(max_length=6, allow_blank=True, default="")
    pattern = serializers.CharField(max_length=40, allow_blank=True)


def _scheme_data(scheme, title_id=None):
    if scheme is None:
        return {"title_id": title_id, "prefix": "", "pattern": "", "draft_prefix": "", "draft_pattern": "",
                "pending": False, "published_at": None, "preview": []}
    return {"title_id": scheme.title_id, "prefix": scheme.prefix, "pattern": scheme.pattern,
            "draft_prefix": scheme.draft_prefix, "draft_pattern": scheme.draft_pattern,
            "pending": (scheme.draft_prefix, scheme.draft_pattern) != (scheme.prefix, scheme.pattern),
            "published_at": scheme.published_at, "preview": numbering.preview(scheme.draft_prefix, scheme.draft_pattern)}


def _space(request, makerspace_id):
    space = space_for(request.user, makerspace_id)
    if not feature_enabled(space, CARD_NUMBERING):
        raise NotFound()  # decision 218: switched off = removed everywhere
    return space


class TitleCardListView(APIView):
    permission_classes = [IsAuthenticated]

    @extend_schema(tags=TAGS, summary="List titles with their card design state and live-card counts",
                   request=None, responses={200: TitleCardSerializer(many=True), **errors(401, 403, 404)})
    def get(self, request, makerspace_id):
        return Response(title_cards.title_rows(space_for(request.user, makerspace_id)))


class CardNumberSchemeListView(APIView):
    permission_classes = [IsAuthenticated]

    @extend_schema(tags=TAGS, summary="Read the card numbering schemes (space default and per title)",
                   request=None, responses={200: NumberSchemeListSerializer, **errors(401, 403, 404)})
    def get(self, request, makerspace_id):
        space = _space(request, makerspace_id)
        rows = {row.title_id: row for row in CardNumberScheme.objects.filter(makerspace=space)}
        return Response({"default": _scheme_data(rows.pop(None, None)),
                         "titles": [_scheme_data(row) for row in rows.values()]})

    @extend_schema(tags=TAGS, summary="Set the space's draft card numbering",
                   description="The draft goes live when the space's default design is published (approved).",
                   request=NumberSchemeWriteSerializer, responses={200: NumberSchemeSerializer, **errors(400, 401, 403, 404)})
    def put(self, request, makerspace_id):
        return Response(_write(request, _space(request, makerspace_id), None))


class CardNumberSchemeTitleView(APIView):
    permission_classes = [IsAuthenticated]

    @extend_schema(tags=TAGS, summary="Set one title's draft card numbering",
                   description="The draft goes live when that title's card design is published (approved).",
                   request=NumberSchemeWriteSerializer, responses={200: NumberSchemeSerializer, **errors(400, 401, 403, 404)})
    def put(self, request, makerspace_id, title_id):
        from apps.makerspaces.models import MembershipTitle
        space = _space(request, makerspace_id)
        get_object_or_404(MembershipTitle, pk=title_id, makerspace=space)
        return Response(_write(request, space, title_id))


@transaction.atomic
def _write(request, space, title_id):
    data = NumberSchemeWriteSerializer(data=request.data)
    data.is_valid(raise_exception=True)
    prefix, pattern = numbering.validate(data.validated_data["prefix"], data.validated_data["pattern"])
    scheme, _ = CardNumberScheme.objects.select_for_update().get_or_create(makerspace=space, title_id=title_id)
    scheme.draft_prefix, scheme.draft_pattern = prefix, pattern
    scheme.save(update_fields=["draft_prefix", "draft_pattern", "updated_at"])
    audit.record(request.user, "card_number_scheme.updated", makerspace=space, target=scheme,
                 meta={"scheme_id": scheme.pk, "title_id": title_id})
    return _scheme_data(scheme)
