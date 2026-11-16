"""Exact event authority and assignment-only review projections."""
from django.db.models import Q
from django.shortcuts import get_object_or_404
from drf_spectacular.utils import extend_schema
from rest_framework.response import Response
from apps.events import event_authority
from . import review_workflow
from .admission_models import HackathonApplication
from .api_base import AdminView, ProgrammeCommandThrottle, paginated
from .api_schema import ERRORS, ReviewSerializer, paginated_schema
from .api_schema_staff import AssignmentResultSerializer, ReviewApplicationSerializer
from .review_models import ApplicationReviewAssignment, ApplicationDecision
from .review_projection import project_application, project_assignment, project_review_result, require_current_assignment
from .admission_errors import ProgrammeError
from .serializers_commands import ReviewAssignInput, ReviewInput


class ApplicationListView(AdminView):
    @extend_schema(tags=["Event programme review"], request=None, responses={200: paginated_schema("ProgrammeApplicationPage", ReviewApplicationSerializer), **ERRORS})
    def get(self, request, pk):
        event, config = self.admin_target(request, pk)
        rows = HackathonApplication.objects.filter(event=event).exclude(state="draft").order_by("submitted_at", "pk")
        if not event_authority.can(request.user, event, None):
            assignments = ApplicationReviewAssignment.objects.filter(event=event, reviewer=request.user).exclude(state="recused")
            rows = rows.filter(Q(pk__in=assignments.values("application_id")) | Q(cohort_id__in=assignments.values("cohort_id")))
            allowed_ids = set()
            for assignment in assignments:
                try:
                    require_current_assignment(assignment, config=config)
                except ProgrammeError:
                    continue
                if assignment.application_id:
                    allowed_ids.add(assignment.application_id)
                else:
                    allowed_ids.update(assignment.cohort.applications.values_list("pk", flat=True))
            rows = rows.filter(pk__in=allowed_ids)
        def project(app):
            result = project_application(app, config)
            own_review = ApplicationReviewAssignment.objects.filter(event=event, reviewer=request.user).filter(
                Q(application=app) | Q(cohort_id=app.cohort_id, cohort_id__isnull=False)).exclude(state="recused").order_by("-round", "-pk").first()
            result.update(cohort_id=app.cohort_id, cohort_version=app.cohort.version if app.cohort_id else None,
                          review_id=own_review.pk if own_review else None, rsvp_due_at=app.rsvp_due_at)
            if event_authority.can(request.user, event, None):
                draft = ApplicationDecision.objects.filter(batch__event=event, batch__state="draft", active_draft=True).filter(
                    Q(application=app) | Q(cohort_id=app.cohort_id, cohort_id__isnull=False)).first()
                result["draft_batch_id"] = draft.batch_id if draft else None
            return result
        return paginated(request, rows, project)


class ReviewAssignView(AdminView):
    throttle_classes = [ProgrammeCommandThrottle]

    @extend_schema(tags=["Event programme review"], request=ReviewAssignInput,
                   responses={200: AssignmentResultSerializer, **ERRORS})
    def post(self, request, pk):
        self.admin_target(request, pk)
        return Response(review_workflow.assign(event_id=pk, actor=request.user, data=self.command_data(request, ReviewAssignInput)))


class ReviewView(AdminView):
    throttle_classes = [ProgrammeCommandThrottle]

    @extend_schema(tags=["Event programme review"], request=None, responses={200: ReviewSerializer, **ERRORS})
    def get(self, request, pk, review_id):
        event, config = self.admin_target(request, pk)
        row = get_object_or_404(ApplicationReviewAssignment, event=event, pk=review_id, reviewer=request.user)
        return Response(project_assignment(row, actor=request.user, config=config))

    @extend_schema(tags=["Event programme review"], request=ReviewInput, responses={200: ReviewSerializer, **ERRORS})
    def patch(self, request, pk, review_id):
        event, config = self.admin_target(request, pk)
        row = review_workflow.submit(event_id=pk, review_id=review_id, actor=request.user, data=self.command_data(request, ReviewInput))
        return Response(project_review_result(row, actor=request.user, config=config))
