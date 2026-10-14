from drf_spectacular.utils import extend_schema
from rest_framework.response import Response

from apps.events.event_permissions import EDIT_DETAILS, MANAGE_REGISTRATIONS
from apps.events.feedback_templates import apply_feedback_template
from apps.events.serializers_admin import EventAdminSerializer, EventRegistrationAdminSerializer, EmptyActionSerializer
from apps.events.serializers_feedback import FeedbackSurveySerializer
from apps.events.serializers_staff_tools import (
    EventDuplicateSerializer, FeedbackTemplateSerializer, RegistrationAnswersSerializer,
)
from apps.events.services_clone import duplicate_event
from apps.events.services_registration_tools import edit_registration_answers, restore_registration
from apps.events.views_admin_events import _manageable_event, _manageable_registration
from apps.events.views_admin_registrations import _RegistrationActionView
from apps.events.registration_view_errors import REGISTRATION_ACTION_ERRORS
from apps.admin_api.permissions import IsActiveStaff
from rest_framework.views import APIView
from apps.hardware_requests.exceptions import ErrorSerializer

ERRORS = {code: ErrorSerializer for code in (400, 401, 403, 404, 409, 503)}


class EventDuplicateView(APIView):
    permission_classes = [IsActiveStaff]

    @extend_schema(tags=["Admin events"], summary="Duplicate event into a standalone draft",
                   request=EventDuplicateSerializer, responses={201: EventAdminSerializer, **ERRORS})
    def post(self, request, pk):
        event = _manageable_event(request.user, pk, EDIT_DETAILS)
        serializer = EventDuplicateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        clone = duplicate_event(event, actor=request.user, **serializer.validated_data)
        return Response(EventAdminSerializer(clone, context={"request": request}).data, status=201)


class EventRegistrationAnswersView(APIView):
    permission_classes = [IsActiveStaff]

    @extend_schema(tags=["Admin events"], summary="Edit validated custom registration answers",
                   request=RegistrationAnswersSerializer,
                   responses={200: EventRegistrationAdminSerializer, **REGISTRATION_ACTION_ERRORS})
    def patch(self, request, pk):
        registration = _manageable_registration(request.user, pk, MANAGE_REGISTRATIONS)
        serializer = RegistrationAnswersSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        edited = edit_registration_answers(registration, actor=request.user, **serializer.validated_data)
        # This edit carries no finance authority or payment summary.
        return Response(EventRegistrationAdminSerializer(edited).data)


class EventRegistrationRestoreView(_RegistrationActionView):
    operation = staticmethod(restore_registration)

    @extend_schema(tags=["Admin events"], summary="Exactly restore a cancellation within five minutes",
                   request=EmptyActionSerializer,
                   responses={200: EventRegistrationAdminSerializer, **REGISTRATION_ACTION_ERRORS})
    def post(self, request, pk):
        return self.execute(request, pk)


class EventFeedbackTemplateView(APIView):
    permission_classes = [IsActiveStaff]

    @extend_schema(tags=["Admin events"], summary="Apply a feedback template before any response",
                   request=FeedbackTemplateSerializer,
                   responses={200: FeedbackSurveySerializer, **ERRORS})
    def post(self, request, pk):
        event = _manageable_event(request.user, pk, EDIT_DETAILS)
        serializer = FeedbackTemplateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        survey = apply_feedback_template(event, actor=request.user, **serializer.validated_data)
        survey.response_count = 0
        return Response(FeedbackSurveySerializer(survey).data)
