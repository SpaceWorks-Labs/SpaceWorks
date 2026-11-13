"""Staff decision batches: private preview/stage and explicit release."""
from django.shortcuts import get_object_or_404
from drf_spectacular.utils import extend_schema
from rest_framework.response import Response
from . import admission_decisions, admission_rsvp
from .admission_errors import check_version
from .admission_models import HackathonApplication, HackathonApplicationCohort
from .api_base import AdminView, ProgrammeCommandThrottle
from .api_schema import AggregateSerializer, BatchSerializer, ERRORS
from .api_schema_details import PreviewSerializer
from .capacity_admission import occupancy, preview
from .review_models import ApplicationDecisionBatch
from .serializers_commands import BatchInput, ExtendRsvpInput, StageInput, StaffRsvpInput


def project_batch(row):
    return {"id": row.pk, "event_id": row.event_id, "version": row.version, "state": row.state,
            "allowed_actions": ["release", "cancel"] if row.state == "draft" else [],
            "decisions": [{"id": d.pk, "application_id": d.application_id, "cohort_id": d.cohort_id,
                           "outcome": d.outcome, "reason_code": d.reason_code, "stage_id": d.stage_id,
                           "expected_version": d.expected_subject_version, "sent_revision": d.sent_revision}
                          for d in row.decisions.order_by("pk")]}


def staff_application(row):
    return {"id": row.pk, "event_id": row.event_id, "version": row.version, "state": row.state,
            "allowed_actions": [], "rsvp_due_at": row.rsvp_due_at}


class DecisionPreviewView(AdminView):
    @extend_schema(tags=["Event programme review"], request=StageInput,
                   responses={200: PreviewSerializer, **ERRORS})
    def post(self, request, pk):
        event, config = self.admin_target(request, pk)
        data = self.command_data(request, StageInput)
        groups = []
        for item in data["decisions"]:
            model = HackathonApplicationCohort if "cohort_id" in item else HackathonApplication
            subject = get_object_or_404(model, event=event, pk=item.get("cohort_id", item.get("application_id")))
            check_version(subject, item["expected_version"])
            if item["outcome"] == "offer":
                groups.append((subject.pk, subject.applications.count() if isinstance(subject, HackathonApplicationCohort) else 1))
        return Response({"counts": occupancy(event, config), "selection": preview(event, config, groups)})


class DecisionStageView(AdminView):
    throttle_classes = [ProgrammeCommandThrottle]

    @extend_schema(tags=["Event programme review"], request=StageInput, responses={201: BatchSerializer, **ERRORS})
    def post(self, request, pk):
        self.admin_target(request, pk)
        row = admission_decisions.stage(event_id=pk, actor=request.user, data=self.command_data(request, StageInput))
        return Response(project_batch(row), status=201)


class DecisionReleaseView(AdminView):
    throttle_classes = [ProgrammeCommandThrottle]
    cancel = False

    @extend_schema(tags=["Event programme review"], request=BatchInput, responses={200: BatchSerializer, **ERRORS})
    def post(self, request, pk):
        self.admin_target(request, pk)
        row = admission_decisions.finish_batch(event_id=pk, actor=request.user, data=self.command_data(request, BatchInput), cancel=self.cancel)
        return Response(project_batch(row))


class DecisionCancelView(DecisionReleaseView):
    cancel = True


class DecisionDetailView(AdminView):
    @extend_schema(tags=["Event programme review"], request=None, responses={200: BatchSerializer, **ERRORS})
    def get(self, request, pk, batch_id):
        event, _ = self.admin_target(request, pk)
        return Response(project_batch(get_object_or_404(ApplicationDecisionBatch, pk=batch_id, event=event)))


class ExtendRsvpView(AdminView):
    throttle_classes = [ProgrammeCommandThrottle]

    @extend_schema(tags=["Event programme review"], request=ExtendRsvpInput, responses={200: AggregateSerializer, **ERRORS})
    def post(self, request, pk, application_id):
        self.admin_target(request, pk)
        return Response(staff_application(admission_rsvp.extend_rsvp(event_id=pk, application_id=application_id,
            actor=request.user, data=self.command_data(request, ExtendRsvpInput))))


class StaffRsvpView(AdminView):
    throttle_classes = [ProgrammeCommandThrottle]

    @extend_schema(tags=["Event programme review"], request=StaffRsvpInput, responses={200: AggregateSerializer, **ERRORS})
    def post(self, request, pk, application_id):
        self.admin_target(request, pk)
        return Response(staff_application(admission_rsvp.rsvp(event_id=pk, application_id=application_id,
            actor=request.user, data=self.command_data(request, StaffRsvpInput))))
