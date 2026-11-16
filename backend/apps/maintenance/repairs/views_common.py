"""Shared lookups for the repairs routes: every row through rbac's makerspace scope first."""

from django.db.models import Prefetch
from django.shortcuts import get_object_or_404
from drf_spectacular.utils import OpenApiResponse
from rest_framework.pagination import PageNumberPagination

from apps.accounts import rbac
from apps.hardware_requests.exceptions import ErrorSerializer
from apps.makerspaces.models import Makerspace

from . import areas, authority

ERRORS = {code: OpenApiResponse(ErrorSerializer) for code in (400, 401, 403, 404, 409)}
TAGS = ["Repairs"]


class IssuePagination(PageNumberPagination):
    page_size = 24


def space_for(actor, makerspace_id):
    return get_object_or_404(rbac.scope_by_makerspace(actor, Makerspace.objects.all(), makerspace_field="pk"),
                             pk=makerspace_id)


def require_any(space, keys_by_area):
    if not areas.areas_on(space, keys_by_area):
        areas.refuse(" / ".join(keys_by_area.values()))


def require_issues(space):
    """The issue queue exists while any area has reporting or repairs switched on."""
    if not any(areas.area_on(space, area) for area in areas.AREAS):
        areas.refuse("repairs / issue reporting")


def issue_rows():
    from apps.maintenance.models import IssueAssignment, IssueReport
    return IssueReport.objects.select_related("makerspace", "machine", "product", "asset", "room").prefetch_related(
        Prefetch("assignments", queryset=IssueAssignment.objects.select_related("contact", "person")))


def issue_for(actor, pk):
    """An issue this actor may read, or 404 (never discloses another space's rows)."""
    row = get_object_or_404(rbac.scope_by_makerspace(actor, issue_rows()), pk=pk)
    if not authority.visible_issues(actor, row.makerspace).filter(pk=row.pk).exists():
        from django.http import Http404
        raise Http404()
    return row


def detail(request, issue):
    from .serializers_issues import IssueReportDetailSerializer
    issue = issue_rows().prefetch_related("events__actor", "events__contact", "photos", "dispatches__contact",
                                          "parts").get(pk=issue.pk)
    return IssueReportDetailSerializer(issue, context={"request": request, "actor": request.user}).data
