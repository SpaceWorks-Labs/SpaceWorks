"""Staff operation endpoints. G mounts these only after route policies are installed."""

from drf_spectacular.utils import OpenApiExample, extend_schema
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.admin_api.permissions import IsActiveStaff
from apps.events import event_authority
from apps.events.event_permissions import CHECK_IN, EDIT_DETAILS, VIEW

from .forms import _permission, project_form, save_form, validate_form_preview
from . import openapi_examples as examples
from .live import project_live
from .publishing import project_publishing, save_publishing
from .readiness import project_readiness
from .serializers import (
    ERRORS, FormPutInput, FormSelector, FormSerializer, FormValidationInput, FormValidationSerializer,
    LiveSerializer, PublishingInput, PublishingSerializer, ReadinessSerializer,
)


def private_response(data):
    return Response(data, headers={"Cache-Control": "private, no-store"})


class ReadinessView(APIView):
    permission_classes = [IsActiveStaff]

    @extend_schema(tags=["Event programme"], request=None, responses={200: ReadinessSerializer, **ERRORS},
                   examples=[OpenApiExample("Permission-filtered readiness", value=examples.READINESS, response_only=True)])
    def get(self, request, pk):
        event = event_authority.get_event(request.user, pk, VIEW)
        return private_response(ReadinessSerializer(project_readiness(event, actor=request.user)).data)


class EventDayView(APIView):
    permission_classes = [IsActiveStaff]

    @extend_schema(tags=["Event programme"], request=None, responses={200: LiveSerializer, **ERRORS},
                   examples=[OpenApiExample("Event-day arrivals", value=examples.LIVE, response_only=True)])
    def get(self, request, pk):
        event = event_authority.get_event(request.user, pk, CHECK_IN)
        return private_response(LiveSerializer(project_live(event, actor=request.user)).data)


class PublishingView(APIView):
    permission_classes = [IsActiveStaff]

    @extend_schema(tags=["Event programme"], request=None, responses={200: PublishingSerializer, **ERRORS},
                   examples=[OpenApiExample("Draft remains unreleased", value=examples.PUBLISHING, response_only=True)])
    def get(self, request, pk):
        event = event_authority.get_event(request.user, pk, EDIT_DETAILS)
        return private_response(project_publishing(event, actor=request.user))

    @extend_schema(tags=["Event programme"], request=PublishingInput,
                   responses={200: PublishingSerializer, **ERRORS})
    def patch(self, request, pk):
        event = event_authority.get_event(request.user, pk, EDIT_DETAILS)
        payload = PublishingInput(data=request.data)
        payload.is_valid(raise_exception=True)
        result = save_publishing(event, actor=request.user, data=payload.validated_data)
        return private_response(result)


class EventFormView(APIView):
    permission_classes = [IsActiveStaff]

    @extend_schema(tags=["Event forms"], request=None, parameters=[FormSelector], responses={200: FormSerializer, **ERRORS},
                   examples=[OpenApiExample("Versioned form", value=examples.FORM_READ, response_only=True)])
    def get(self, request, pk, form_key):
        event = event_authority.get_event(request.user, pk, _permission(form_key))
        selection = FormSelector(data=request.query_params)
        selection.is_valid(raise_exception=True)
        return private_response(project_form(event, actor=request.user, key=form_key, selector=selection.validated_data))

    @extend_schema(tags=["Event forms"], request=FormPutInput, responses={200: FormSerializer, **ERRORS},
                   examples=[OpenApiExample("Save form questions", value=examples.FORM_PUT, request_only=True)])
    def put(self, request, pk, form_key):
        event = event_authority.get_event(request.user, pk, _permission(form_key))
        payload = FormPutInput(data=request.data)
        payload.is_valid(raise_exception=True)
        return private_response(save_form(event, actor=request.user, key=form_key, data=payload.validated_data))


class EventFormValidateView(APIView):
    permission_classes = [IsActiveStaff]

    @extend_schema(tags=["Event forms"], request=FormValidationInput,
                   responses={200: FormValidationSerializer, **ERRORS}, examples=[
                       OpenApiExample("Partial sample validation", value=examples.FORM_VALIDATION_INPUT, request_only=True),
                       OpenApiExample("Visible sample fields", value=examples.FORM_VALIDATION_RESULT, response_only=True)])
    def post(self, request, pk, form_key):
        event = event_authority.get_event(request.user, pk, _permission(form_key))
        payload = FormValidationInput(data=request.data)
        payload.is_valid(raise_exception=True)
        result = validate_form_preview(event, actor=request.user, key=form_key, **payload.validated_data)
        return private_response(result)
