"""Tenant-owned approved template bindings; platform bindings stay in /control/."""
from django.db import IntegrityError
from django.shortcuts import get_object_or_404
from drf_spectacular.utils import extend_schema
from rest_framework.exceptions import APIException
from rest_framework.pagination import PageNumberPagination
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.integrations.models import WhatsAppTemplateBinding
from apps.openapi_errors import errors
from .projections import PROJECTION_KEYS
from .serializers import MessagingCatalogEntrySerializer, WhatsAppBindingSerializer, WhatsAppBindingPageSerializer
from .templates import WHATSAPP_LANGUAGES, save_binding
from .views_settings import staff_space


class BindingConflict(APIException):
    status_code = 409
    default_detail = {"code": "binding_exists", "detail": "This event and audience already has a binding."}


def _save(actor, space, values, pk=None):
    try:
        return save_binding(actor, space, values, pk)
    except IntegrityError as exc:
        raise BindingConflict() from exc


class WhatsAppTemplateListView(APIView):
    permission_classes = [IsAuthenticated]

    @extend_schema(tags=["Messaging"], responses={200: WhatsAppBindingPageSerializer, **errors(401, 403, 404)})
    def get(self, request, makerspace_id):
        space = staff_space(request.user, makerspace_id)
        paginator = PageNumberPagination()
        paginator.page_size = 24
        rows = WhatsAppTemplateBinding.objects.filter(makerspace=space).order_by("pk")
        return paginator.get_paginated_response(WhatsAppBindingSerializer(paginator.paginate_queryset(rows, request), many=True).data)

    @extend_schema(tags=["Messaging"], request=WhatsAppBindingSerializer,
                   responses={201: WhatsAppBindingSerializer, **errors(400, 401, 403, 404, 409, 423, 503)})
    def post(self, request, makerspace_id):
        space = staff_space(request.user, makerspace_id)
        serializer = WhatsAppBindingSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        row = _save(request.user, space, serializer.validated_data)
        return Response(WhatsAppBindingSerializer(row).data, status=201)


class WhatsAppTemplateDetailView(APIView):
    permission_classes = [IsAuthenticated]

    @extend_schema(tags=["Messaging"], request=WhatsAppBindingSerializer,
                   responses={200: WhatsAppBindingSerializer, **errors(400, 401, 403, 404, 409, 423, 503)})
    def patch(self, request, makerspace_id, pk):
        space = staff_space(request.user, makerspace_id)
        row = get_object_or_404(WhatsAppTemplateBinding, makerspace=space, pk=pk)
        serializer = WhatsAppBindingSerializer(row, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        return Response(WhatsAppBindingSerializer(_save(request.user, space, serializer.validated_data, pk)).data)

    @extend_schema(tags=["Messaging"], responses={204: None, **errors(401, 403, 404, 423, 503)})
    def delete(self, request, makerspace_id, pk):
        space = staff_space(request.user, makerspace_id)
        save_binding(request.user, space, {}, pk, delete=True)
        return Response(status=204)


class WhatsAppTemplateCatalogView(APIView):
    permission_classes = [IsAuthenticated]

    @extend_schema(tags=["Messaging"], responses={200: MessagingCatalogEntrySerializer(many=True), **errors(401, 403, 404)})
    def get(self, request, makerspace_id):
        staff_space(request.user, makerspace_id)
        return Response([{"feature": feature, "event": event, "audience": audience,
                          "allowed_projection_keys": keys, "supported_languages": WHATSAPP_LANGUAGES}
                         for (feature, event, audience), keys in sorted(PROJECTION_KEYS.items())])
