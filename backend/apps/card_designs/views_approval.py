"""The card-design approval levels of one space (#136): the space level and each organisation.

Four levels decide whether a design edit needs a Space Manager's approval, most specific
first: event, ID programme, organisation, space. The programme and event levels are set on
the programme and the event; this route reads and writes the two broad ones for both
groups (membership + programme cards, event cards + tickets).

Who writes: the host space's settings authority for that group (Space Manager or a
`card_designs.approval` grant), never an organisation governor -- an organisation level
overrides the space, so letting an organisation write it would let it loosen the space's
own rule. Clearing a level (`required: null`) makes it inherit again.
"""
from django.http import Http404
from django.shortcuts import get_object_or_404
from drf_spectacular.utils import extend_schema
from rest_framework import serializers
from rest_framework.exceptions import ValidationError
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.accounts import rbac
from apps.makerspaces.platform import module_enabled
from apps.openapi_errors import errors

from .approval import DEFAULTS, level_value, set_level
from .switches import EVENT_CARDS, EVENT_TICKETS

TAGS = ["Card designs"]
GROUP_MODULES = {"membership": "membership", "event": "events"}
MAX_ORGANISATIONS = 200


class ApprovalGroupLevelSerializer(serializers.Serializer):
    group = serializers.ChoiceField(choices=tuple(GROUP_MODULES))
    available = serializers.BooleanField()
    default = serializers.BooleanField()
    space = serializers.BooleanField(allow_null=True)


class ApprovalOrganisationSerializer(serializers.Serializer):
    id = serializers.IntegerField()
    name = serializers.CharField()
    membership = serializers.BooleanField(allow_null=True)
    event = serializers.BooleanField(allow_null=True)


class ApprovalLevelsSerializer(serializers.Serializer):
    groups = ApprovalGroupLevelSerializer(many=True)
    organisations = ApprovalOrganisationSerializer(many=True)


class ApprovalLevelWriteSerializer(serializers.Serializer):
    group = serializers.ChoiceField(choices=tuple(GROUP_MODULES))
    organization_id = serializers.IntegerField(required=False, allow_null=True, min_value=1)
    required = serializers.BooleanField(allow_null=True)


def _space(actor, makerspace_id):
    from apps.makerspaces.models import Makerspace
    space = get_object_or_404(Makerspace, pk=makerspace_id)
    if not (rbac.can(actor, rbac.Action.APPROVE_CARD_DESIGNS, space.pk)
            or rbac.can(actor, rbac.Action.MANAGE_MEMBER_CARDS, space.pk)):
        raise Http404
    return space


def _group_available(space, group):
    from apps.makerspaces.platform import feature_enabled
    if group == "membership":
        return module_enabled(space, "membership")
    return module_enabled(space, "events") and (feature_enabled(space, EVENT_CARDS)
                                                or feature_enabled(space, EVENT_TICKETS))


def organisations_for(space):
    """Organisations linked to the space, organising its events, or already holding a level."""
    from apps.card_designs.models import CardApprovalSetting
    from apps.organizations.models import Organization
    ids = set(space.organization_links.values_list("organization_id", flat=True))
    ids |= set(CardApprovalSetting.objects.filter(makerspace=space, organization__isnull=False)
               .values_list("organization_id", flat=True))
    if module_enabled(space, "events"):
        from apps.events.organizer_models import EventOrganizer
        ids |= set(EventOrganizer.objects.filter(event__makerspace=space).values_list("organization_id", flat=True)
                   .distinct()[:MAX_ORGANISATIONS])
    return Organization.objects.filter(pk__in=ids).order_by("name", "pk")[:MAX_ORGANISATIONS]


def payload(space):
    groups = [{"group": group, "available": _group_available(space, group), "default": DEFAULTS[group],
               "space": level_value(space, group)} for group in GROUP_MODULES]
    organisations = [{"id": row.pk, "name": row.name,
                      **{group: level_value(space, group, organization=row) for group in GROUP_MODULES}}
                     for row in organisations_for(space)]
    return {"groups": groups, "organisations": organisations}


class CardApprovalLevelsView(APIView):
    permission_classes = [IsAuthenticated]

    @extend_schema(tags=TAGS, summary="The space and organisation approval levels for card designs (#136)",
                   request=None, responses={200: ApprovalLevelsSerializer, **errors(401, 404)})
    def get(self, request, makerspace_id):
        return Response(payload(_space(request.user, makerspace_id)))

    @extend_schema(tags=TAGS, summary="Set or clear one approval level (space or organisation)",
                   request=ApprovalLevelWriteSerializer,
                   responses={200: ApprovalLevelsSerializer, **errors(400, 401, 403, 404)})
    def put(self, request, makerspace_id):
        from apps.makerspaces.settings_authority import assert_setting_write, record_change
        space = _space(request.user, makerspace_id)
        data = ApprovalLevelWriteSerializer(data=request.data)
        data.is_valid(raise_exception=True)
        group, required = data.validated_data["group"], data.validated_data["required"]
        if not _group_available(space, group):
            raise ValidationError({"group": "This kind of card is switched off for this space."})
        organization = None
        if data.validated_data.get("organization_id"):
            organization = next((row for row in organisations_for(space)
                                 if row.pk == data.validated_data["organization_id"]), None)
            if organization is None:
                raise ValidationError({"organization_id": "This organisation has no link to this space."})
        decision = assert_setting_write(request.user, space, GROUP_MODULES[group], "card_designs.approval")
        before = level_value(space, group, organization=organization)
        set_level(request.user, space, group, required, organization=organization)
        if organization is None:
            record_change(request.user, space, GROUP_MODULES[group], "card_designs.approval", before, required,
                          decision)
        return Response(payload(space))
