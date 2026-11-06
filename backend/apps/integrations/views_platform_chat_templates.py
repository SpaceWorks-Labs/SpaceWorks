"""A space's chat message templates in the web superadmin console (#190, parity with /control/).

One body per (feature, event), shared by every chat channel (Telegram, Slack, ...). The
same validation as the /control/ form (``validate_chat_template_string``: a known event and
a template that renders against its sample context). Removing a row returns that event to
the built-in text. Every change is audited.
"""

from django.utils.translation import gettext
from django.core.exceptions import ValidationError as DjangoValidationError
from django.shortcuts import get_object_or_404
from drf_spectacular.utils import extend_schema
from rest_framework import serializers, status
from rest_framework.generics import GenericAPIView
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.accounts.reauthentication_permissions import RecentReauthenticationMixin
from apps.admin_api.permissions import IsActiveSuperAdmin
from apps.audit import services as audit
from apps.integrations.chat_templates import validate_chat_template_string
from apps.integrations.models_chat_templates import ChatTemplate
from apps.makerspaces.models import Makerspace
from apps.openapi_errors import errors

TAGS = ["Platform messaging"]


class ChatTemplateSerializer(serializers.ModelSerializer):
    class Meta:
        model = ChatTemplate
        fields = ("id", "feature", "event", "text_body", "is_active", "updated_at")
        read_only_fields = ("id", "updated_at")

    def validate(self, attrs):
        feature = attrs.get("feature", getattr(self.instance, "feature", None))
        event = attrs.get("event", getattr(self.instance, "event", None))
        try:
            validate_chat_template_string(feature, event, attrs.get("text_body", getattr(self.instance, "text_body", "")))
        except DjangoValidationError as exc:
            raise serializers.ValidationError({"text_body": exc.messages}) from None
        space = self.context["makerspace"]
        clash = ChatTemplate.objects.filter(makerspace=space, feature=feature, event=event)
        if self.instance is not None:
            clash = clash.exclude(pk=self.instance.pk)
        if clash.exists():
            raise serializers.ValidationError({"event": gettext("This event already has a template here.")})
        return attrs


class ChatTemplateListBase(GenericAPIView):
    """Shared with the Space Manager editor (``views_space_chat_templates``); ``_space`` decides who may."""

    serializer_class = ChatTemplateSerializer

    def _space(self, request, makerspace_id):
        return get_object_or_404(Makerspace, pk=makerspace_id)

    @extend_schema(tags=TAGS, summary="List a space's chat message templates",
                   responses={200: ChatTemplateSerializer(many=True), **errors(401, 403, 404)})
    def get(self, request, makerspace_id):
        space = self._space(request, makerspace_id)
        page = self.paginate_queryset(ChatTemplate.objects.filter(makerspace=space))
        return self.get_paginated_response(ChatTemplateSerializer(page, many=True).data)

    @extend_schema(tags=TAGS, summary="Add a chat message template for one event",
                   request=ChatTemplateSerializer, responses={201: ChatTemplateSerializer, **errors(400, 401, 403, 404)})
    def post(self, request, makerspace_id):
        space = self._space(request, makerspace_id)
        body = ChatTemplateSerializer(data=request.data, context={"makerspace": space})
        body.is_valid(raise_exception=True)
        row = body.save(makerspace=space, updated_by=request.user)
        audit.record(request.user, "chat_template.saved", makerspace=row.makerspace, target=row,
                     meta={"via": "console", "feature": row.feature, "event": row.event})
        return Response(ChatTemplateSerializer(row).data, status=status.HTTP_201_CREATED)


class ChatTemplateListCreateView(RecentReauthenticationMixin, ChatTemplateListBase):
    permission_classes = [IsActiveSuperAdmin]


class ChatTemplateDetailBase(APIView):
    def _space(self, request, makerspace_id):
        return get_object_or_404(Makerspace, pk=makerspace_id)

    def _row(self, makerspace_id, pk):
        space = self._space(self.request, makerspace_id)
        return get_object_or_404(ChatTemplate.objects.select_related("makerspace"), pk=pk, makerspace=space)

    @extend_schema(tags=TAGS, summary="Change a chat message template", request=ChatTemplateSerializer,
                   responses={200: ChatTemplateSerializer, **errors(400, 401, 403, 404)})
    def patch(self, request, makerspace_id, pk):
        row = self._row(makerspace_id, pk)
        body = ChatTemplateSerializer(row, data=request.data, partial=True, context={"makerspace": row.makerspace})
        body.is_valid(raise_exception=True)
        row = body.save(updated_by=request.user)
        audit.record(request.user, "chat_template.saved", makerspace=row.makerspace, target=row,
                     meta={"via": "console", "feature": row.feature, "event": row.event})
        return Response(ChatTemplateSerializer(row).data)

    @extend_schema(tags=TAGS, summary="Remove a chat template (the event goes back to the built-in text)",
                   responses={204: None, **errors(401, 403, 404)})
    def delete(self, request, makerspace_id, pk):
        row = self._row(makerspace_id, pk)
        audit.record(request.user, "chat_template.deleted", makerspace=row.makerspace, target=row,
                     meta={"via": "console", "feature": row.feature, "event": row.event})
        row.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)


class ChatTemplateDetailView(RecentReauthenticationMixin, ChatTemplateDetailBase):
    permission_classes = [IsActiveSuperAdmin]
