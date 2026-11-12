"""Import one of the member's OWN hackathon submissions as a profile project (decision 302d).

Account-level: the submission may come from any space the person took part in.

"Own" means the submission's current sealed snapshot lists the caller, i.e. a team they
belonged to when it was submitted -- never a team they merely applied to, never another
member's. Title, summary and the https links are copied (a copy, because the profile owns
its text and may edit it); the project remembers its source by a stored submission id so the
same submission cannot be imported twice. Imported projects are shown like any other (303a: open by default; hide a
project with its own switch).
"""

from urllib.parse import urlsplit

from django.db import transaction
from django.utils.translation import gettext
from drf_spectacular.utils import extend_schema
from rest_framework import serializers
from rest_framework.exceptions import APIException, NotFound, ValidationError
from rest_framework.response import Response

from apps.audit import services as audit
from apps.hardware_requests.exceptions import ErrorSerializer

from .account_profile import account_profile_for
from .account_profile_views import ERRORS, AccountOwnerView
from .models_account_profile import AccountProfile, AccountProject
from .profile_serializers import MAX_PROJECTS

IMPORTABLE_STATES = ("submitted", "locked", "under_review", "judged")


class AlreadyImported(APIException):
    status_code = 409
    default_code = "already_imported"
    default_detail = "This submission is already one of your projects."


def own_submissions(user):
    from apps.events.models import HackathonSubmission, SubmissionSnapshot
    mine = SubmissionSnapshot.objects.filter(sealed_member_ids__contains=[user.pk]).values("pk")
    return HackathonSubmission.objects.filter(
        current_snapshot_id__in=mine, state__in=IMPORTABLE_STATES,
    ).select_related("event__makerspace").order_by("-submitted_at", "-pk")


def _links(submission):
    rows = submission.links.filter(version=submission.links_version).values("kind", "url")
    links = []
    for row in rows:
        parsed = urlsplit(row["url"])
        if parsed.scheme == "https" and parsed.hostname and not parsed.username and not parsed.password:
            links.append({"label": (row["kind"] or "link").title()[:60], "url": row["url"][:500]})
    return links[:10]


@transaction.atomic
def import_submission(user, submission_id, *, makerspace=None):
    profile = AccountProfile.objects.select_for_update().get(pk=account_profile_for(user).pk)
    submission = own_submissions(user).filter(pk=submission_id).first()
    if submission is None:
        raise NotFound()  # not yours, not submitted, or not there: one answer for all three
    if profile.projects.filter(source_submission_id=submission.pk).exists():
        raise AlreadyImported()
    count = profile.projects.count()
    if count >= MAX_PROJECTS:
        raise ValidationError({"projects": gettext("At most 20 projects are allowed.")})
    project = AccountProject.objects.create(
        profile=profile, title=(submission.title or submission.event.title)[:200],
        subtitle=(submission.tagline or "")[:200], description=(submission.description or submission.problem or "")[:4000],
        links=_links(submission), public_visible=True, position=count, source_submission_id=submission.pk,
    )
    audit.record(user, "member.profile_project_imported", makerspace=makerspace, target=user, meta={})
    return project


class ImportableSubmissionSerializer(serializers.Serializer):
    id = serializers.IntegerField()
    title = serializers.CharField()
    event_title = serializers.CharField()
    space_name = serializers.CharField()
    submitted_at = serializers.DateTimeField(allow_null=True)
    already_imported = serializers.BooleanField()


class ImportInput(serializers.Serializer):
    submission_id = serializers.IntegerField(min_value=1)


class ImportedProjectSerializer(serializers.Serializer):
    id = serializers.IntegerField()
    title = serializers.CharField()


class ProjectImportView(AccountOwnerView):
    @extend_schema(tags=["Member profile"], summary="List the caller's own hackathon submissions",
                   request=None, responses={200: ImportableSubmissionSerializer(many=True), **ERRORS})
    def get(self, request, **kwargs):
        user = self.actor(request, **kwargs)
        profile = AccountProfile.objects.filter(user=user).first()
        imported = set(profile.projects.exclude(source_submission_id=None)
                       .values_list("source_submission_id", flat=True)) if profile else set()
        rows = [{"id": row.pk, "title": row.title or row.event.title, "event_title": row.event.title,
                 "space_name": row.event.makerspace.name, "submitted_at": row.submitted_at,
                 "already_imported": row.pk in imported}
                for row in own_submissions(user)[:50]]
        return Response(ImportableSubmissionSerializer(rows, many=True).data)

    @extend_schema(tags=["Member profile"], summary="Import an own submission as a project",
                   request=ImportInput,
                   responses={201: ImportedProjectSerializer, 400: ErrorSerializer,
                              409: ErrorSerializer, **ERRORS})
    def post(self, request, **kwargs):
        user = self.actor(request, **kwargs)
        data = ImportInput(data=request.data)
        data.is_valid(raise_exception=True)
        project = import_submission(user, data.validated_data["submission_id"], makerspace=self.audit_space)
        return Response(ImportedProjectSerializer({"id": project.pk, "title": project.title}).data, status=201)
