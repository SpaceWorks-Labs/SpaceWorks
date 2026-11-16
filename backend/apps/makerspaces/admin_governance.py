"""The /control/ makerspace list: the latest archive-request status per row."""

from django.contrib import admin
from django.db.models import OuterRef, Subquery

from .models import MakerspaceArchiveRequest
from django.utils.translation import gettext_lazy


class MakerspaceGovernanceMixin:
    ordering = ("name", "slug")

    def get_queryset(self, request):
        latest = MakerspaceArchiveRequest.objects.filter(
            makerspace_id=OuterRef("pk")
        ).order_by("-requested_at", "-pk")
        return super().get_queryset(request).annotate(
            governance_request_status=Subquery(latest.values("status")[:1])
        )

    @admin.display(description=gettext_lazy("Archive request"))
    def archive_request_status(self, obj):
        return obj.governance_request_status or "none"
