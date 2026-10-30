"""Archive-request review from the /control/ makerspace list."""

from django.contrib import admin, messages
from django.contrib.admin.helpers import ACTION_CHECKBOX_NAME
from django.core.exceptions import ValidationError
from django.template.response import TemplateResponse
from rest_framework.exceptions import APIException

from . import archive_requests, lifecycle
from .models import MakerspaceArchiveRequest


class MakerspaceLifecycleReviewMixin:
    @admin.action(description="Approve pending archive requests")
    def approve_archive_requests(self, request, queryset):
        return self._review_archive_requests(request, queryset, approve=True)

    @admin.action(description="Decline pending archive requests")
    def decline_archive_requests(self, request, queryset):
        return self._review_archive_requests(request, queryset, approve=False)

    def _review_archive_requests(self, request, queryset, *, approve):
        # This visibility exception belongs only to the selected makerspace action.
        # The archive-request ModelAdmin retains its ordinary tenant scoping.
        spaces = list(queryset)
        pending = list(MakerspaceArchiveRequest.objects.filter(
            makerspace__in=spaces, status=MakerspaceArchiveRequest.Status.PENDING,
        ).select_related("requested_by", "makerspace"))
        action = "approve_archive_requests" if approve else "decline_archive_requests"
        if "confirm_review" not in request.POST:
            return TemplateResponse(request, "admin/makerspaces/lifecycle_review_confirmation.html", {
                **self.admin_site.each_context(request),
                "title": "Approve archive requests" if approve else "Decline archive requests",
                "spaces": spaces,
                "requests": [{
                    "id": item.pk, "requested_at": item.requested_at,
                    "username": item.requested_by.username if item.requested_by else "",
                    "reason": item.reason,
                    **({"impact": lifecycle.archive_impact(item.makerspace)}
                       if approve else {}),
                } for item in pending],
                "approve": approve, "opts": self.model._meta, "action_name": action,
                "action_checkbox_name": ACTION_CHECKBOX_NAME,
            })
        for item in pending:
            try:
                if approve:
                    archive_requests.approve(item, request.user)
                else:
                    archive_requests.decline(item, request.user, request.POST.get("resolution_note", ""))
            except (APIException, ValidationError) as exc:
                self.message_user(request, f"Request {item.pk}: {exc}", level=messages.ERROR)
            else:
                self.message_user(request, f"Resolved archive request {item.pk}.", level=messages.SUCCESS)
