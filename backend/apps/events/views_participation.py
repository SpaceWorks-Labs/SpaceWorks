"""Lane L21a routes: per-event switches, attendance confirmation and re-accepting a declined registration."""
from django.db.models import Count, Q
from django.shortcuts import get_object_or_404
from drf_spectacular.utils import extend_schema
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from apps.admin_api.permissions import IsActiveStaff
from apps.audit import services as audit

from . import attendance_confirmation, event_authority
from .hackathons.api_base import ProgrammeCommandThrottle, ProgrammeView
from .hackathons.api_schema import ERRORS
from .models import Event, EventRegistration
from .models_participation import EventAttendanceReply, EventAttendanceRound, EventParticipationSettings
from .serializers_participation import (
    AttendanceReplyInput, AttendanceRoundSerializer, AttendanceSendInput, AttendanceSummarySerializer,
    OwnAttendanceSerializer, ParticipationSettingsSerializer, ReacceptResultSerializer,
)

SWITCHES = ("stage_advanced_email", "attendance_free_on_no", "crew_signup_open", "crew_approval_required",
            "crew_public_section")
TAGS = ["Event participation"]


def project_settings(row):
    return {key: getattr(row, key) for key in SWITCHES}


class ParticipationSettingsView(ProgrammeView):
    permission_classes = [IsActiveStaff]

    @extend_schema(tags=TAGS, request=None, responses={200: ParticipationSettingsSerializer, **ERRORS})
    def get(self, request, pk):
        event = event_authority.get_event(request.user, pk, "manage_registrations")
        return Response(project_settings(EventParticipationSettings.for_event(event)))

    @extend_schema(tags=TAGS, request=ParticipationSettingsSerializer,
                   responses={200: ParticipationSettingsSerializer, **ERRORS},
                   summary="Per-event switches: stage email, free the place on No, crew sign-up and section")
    def patch(self, request, pk):
        from .services_write_boundary import write_boundary
        event = event_authority.get_event(request.user, pk, None)
        data = ParticipationSettingsSerializer(data=request.data)
        data.is_valid(raise_exception=True)
        with write_boundary(event, actor=request.user):
            event_authority.require(request.user, Event.objects.get(pk=pk), None)
            row, _ = EventParticipationSettings.objects.select_for_update().get_or_create(
                event=event, defaults={"makerspace": event.makerspace})
            changed = sorted(key for key, value in data.validated_data.items() if getattr(row, key) != value)
            for key, value in data.validated_data.items():
                setattr(row, key, value)
            row.updated_by = request.user
            row.save()
            audit.record(request.user, "event.participation_settings_updated", makerspace=event.makerspace,
                         target=event, meta={"event_id": event.pk, "changed": changed})
        return Response(project_settings(row))


class AttendanceStaffView(ProgrammeView):
    permission_classes = [IsActiveStaff]
    throttle_classes = [ProgrammeCommandThrottle]

    def summary(self, event):
        replies = EventAttendanceReply.objects.filter(event=event)
        counts = replies.aggregate(asked=Count("pk"), yes=Count("pk", filter=Q(answer="yes")),
                                   no=Count("pk", filter=Q(answer="no")), pending=Count("pk", filter=Q(answer="")),
                                   released=Count("pk", filter=Q(effect__in=("released", "due_case"))),
                                   left_to_staff=Count("pk", filter=Q(effect="left_to_staff")))
        rounds = EventAttendanceRound.objects.filter(event=event).order_by("-created_at")[:10]
        last = rounds[0] if rounds else None
        return {**counts, "next_send_at": last.created_at + attendance_confirmation.INTERVAL if last else None,
                "free_on_no": EventParticipationSettings.for_event(event).attendance_free_on_no,
                "rounds": AttendanceRoundSerializer(rounds, many=True).data}

    @extend_schema(tags=TAGS, request=None, responses={200: AttendanceSummarySerializer, **ERRORS})
    def get(self, request, pk):
        event = event_authority.get_event(request.user, pk, "manage_registrations")
        attendance_confirmation.require_feature(event)
        return Response(self.summary(event))

    @extend_schema(tags=TAGS, request=AttendanceSendInput, responses={201: AttendanceSummarySerializer, **ERRORS},
                   summary="Ask registered people whether they are still coming (staff only; 12 hours apart)")
    def post(self, request, pk):
        event = event_authority.get_event(request.user, pk, "manage_registrations")
        data = AttendanceSendInput(data=request.data)
        data.is_valid(raise_exception=True)
        attendance_confirmation.send(event, actor=request.user, kind=data.validated_data["kind"])
        return Response(self.summary(event), status=201)


class AttendanceMemberView(ProgrammeView):
    permission_classes = [IsAuthenticated]
    throttle_classes = [ProgrammeCommandThrottle]

    def own(self, request, pk):
        reply = get_object_or_404(EventAttendanceReply.objects.select_related("event__makerspace", "registration"),
                                  event_id=pk, registration__member=request.user)
        attendance_confirmation.require_feature(reply.event)
        return reply

    def project(self, reply):
        event = reply.event
        return {"event_id": event.pk, "event_title": event.title, "starts_at": event.starts_at,
                "registration_id": reply.registration_id, "answer": reply.answer or None, "note": reply.note,
                "replied_at": reply.replied_at, "effect": reply.effect,
                "free_on_no": EventParticipationSettings.for_event(event).attendance_free_on_no}

    @extend_schema(tags=TAGS, request=None, responses={200: OwnAttendanceSerializer, **ERRORS})
    def get(self, request, pk):
        return Response(self.project(self.own(request, pk)))

    @extend_schema(tags=TAGS, request=AttendanceReplyInput, responses={200: OwnAttendanceSerializer, **ERRORS},
                   summary="Answer \"Are you still coming?\" with an optional note to the organisers")
    def post(self, request, pk):
        reply = self.own(request, pk)
        data = AttendanceReplyInput(data=request.data)
        data.is_valid(raise_exception=True)
        attendance_confirmation.reply(reply.registration, actor=request.user, **data.validated_data)
        return Response(self.project(self.own(request, pk)))


class RegistrationReacceptView(ProgrammeView):
    permission_classes = [IsActiveStaff]
    throttle_classes = [ProgrammeCommandThrottle]

    @extend_schema(tags=TAGS, request=None, responses={200: ReacceptResultSerializer, **ERRORS},
                   summary="Re-accept a declined registration when a place is free")
    def post(self, request, pk, registration_id):
        from apps.payments.models import Payment
        from .services_registration_state import reaccept_registration
        event = event_authority.get_event(request.user, pk, "manage_registrations")
        registration = get_object_or_404(EventRegistration, pk=registration_id, event=event)
        row = reaccept_registration(registration, actor=request.user)
        due = Payment.objects.filter(subject_type=Payment.SubjectType.EVENT_REGISTRATION, subject_id=row.pk,
                                     status=Payment.Status.PENDING).exists()
        return Response({"id": row.pk, "status": row.status, "payment_due": due})

