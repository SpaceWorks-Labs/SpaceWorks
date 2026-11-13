"""/control/ review of hosting requests: read-only rows, accept/reject actions.

Every decision goes through ``workflow``; nothing here assigns ``status``. Accepting only
marks the request accepted. "Create makerspace" re-authenticates and then opens the
existing Add makerspace form pre-filled; the add form records the link on save.
"""

from urllib.parse import urlencode

from django.contrib import admin, messages
from django.contrib.admin.helpers import ACTION_CHECKBOX_NAME
from django.core.exceptions import PermissionDenied as DjangoPermissionDenied
from django.shortcuts import get_object_or_404, redirect
from django.template.response import TemplateResponse
from django.urls import path, reverse
from django.utils.html import format_html
from rest_framework.exceptions import APIException
from unfold.admin import ModelAdmin

from apps.accounts.reauthentication_control import RecentReauthenticationAdminMixin
from apps.hosting_requests import prefill, workflow
from apps.hosting_requests.availability import admin_available
from apps.hosting_requests.models import HostingRequest
from config.admin_access import SuperuserOnlyModelAdmin
from django.utils.translation import gettext_lazy

TEMPLATE = "admin/hosting_requests/decision_confirmation.html"
OWNER_NOTE = (
    "You may set up the space with its own organization instead: clear Owner organization "
    "and enter a name (both are allowed). If you are asked to verify again, re-open "
    "Create makerspace from this request."
)


def _error_detail(exc):
    detail = getattr(exc, "detail", None)
    if isinstance(detail, dict):
        detail = detail.get("detail") or next(iter(detail.values()), "")
    if isinstance(detail, list):
        detail = " ".join(str(item) for item in detail)
    return str(detail or exc)


def _space_label(makerspace):
    if makerspace is None:
        return "(deleted)"
    return str(makerspace)


@admin.register(HostingRequest)
class HostingRequestAdmin(RecentReauthenticationAdminMixin, SuperuserOnlyModelAdmin, ModelAdmin):
    actions = ["approve_and_create_selected", "accept_selected", "request_changes_selected", "reject_selected"]
    list_display = ("space_name", "requested_kind", "applicant_email", "source", "status", "inviter_summary",
                    "created_at", "verified_at")
    list_filter = ("status", "source", "requested_kind")
    search_fields = ("space_name", "applicant_email", "applicant_name")
    # Makerspace links are shown through the summaries below.
    readonly_fields = (
        *(field.name for field in HostingRequest._meta.concrete_fields
          if field.name not in ("inviter_makerspace", "created_makerspace")),
        "inviter_summary", "owner_choice_summary", "create_makerspace_link",
    )

    def has_module_permission(self, request):
        return admin_available() and super().has_module_permission(request)

    def has_view_permission(self, request, obj=None):
        return admin_available() and super().has_view_permission(request, obj)

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False

    @admin.display(description=gettext_lazy("Inviter"))
    def inviter_summary(self, obj):
        who = f" by {obj.invited_by}" if obj.invited_by_id else ""
        if obj.inviter_kind == HostingRequest.InviterKind.MAKERSPACE:
            return f"Invited via makerspace {_space_label(obj.inviter_makerspace)}{who}"
        if obj.inviter_kind == HostingRequest.InviterKind.ORGANIZATION:
            return f"Invited via organization {obj.inviter_organization or '(deleted)'}{who}"
        return "Public form"

    @admin.display(description=gettext_lazy("Owner organization"))
    def owner_choice_summary(self, obj):
        return f"{prefill.owner_choice_summary(obj)} {OWNER_NOTE}"

    @admin.display(description=gettext_lazy("Create makerspace"))
    def create_makerspace_link(self, obj):
        if obj.created_makerspace_id:
            return f"Created: {_space_label(obj.created_makerspace)}"
        if obj.status != HostingRequest.Status.ACCEPTED:
            return "Available once the request is accepted."
        url = reverse("admin:hosting_requests_hostingrequest_create_makerspace", args=[obj.pk])
        return format_html('<a class="button" href="{}">Create makerspace</a>', url)

    def get_urls(self):
        # Registered BEFORE the defaults: "<path:object_id>/" would otherwise swallow it.
        custom = [path(
            "<int:pk>/create-makerspace/",
            self.admin_site.admin_view(self.create_makerspace_view),
            name="hosting_requests_hostingrequest_create_makerspace",
        )]
        return custom + super().get_urls()

    def create_makerspace_view(self, request, pk):
        from apps.accounts.reauthentication import require_recent_reauth

        if not (admin_available() and self._has_superuser_access(request)):
            raise DjangoPermissionDenied()
        row = get_object_or_404(HostingRequest, pk=pk)
        if row.status != HostingRequest.Status.ACCEPTED or row.created_makerspace_id:
            self.message_user(request, "Only an accepted request with no makerspace yet can be set up.",
                              messages.ERROR)
            return redirect(reverse("admin:hosting_requests_hostingrequest_change", args=[pk]))
        try:
            require_recent_reauth(request)
        except APIException:
            return redirect("/mfa/reauth/?" + urlencode({"next": request.path}))
        return redirect(prefill.add_url(row))

    def _confirm(self, request, rows, *, action_name, needs_reason, title, submit_label, reason_label=""):
        return TemplateResponse(request, TEMPLATE, {
            **self.admin_site.each_context(request),
            "title": title, "hosting_requests": rows, "opts": self.model._meta,
            "action_name": action_name, "action_checkbox_name": ACTION_CHECKBOX_NAME,
            "needs_reason": needs_reason, "submit_label": submit_label, "reason_label": reason_label,
        })

    def _decide(self, request, rows, decide, done):
        count = 0
        for row in rows:
            try:
                decide(row)
            except APIException as exc:
                self.message_user(request, f"{row.space_name}: {_error_detail(exc)}", messages.ERROR)
            else:
                count += 1
        if count:
            self.message_user(request, f"{done} {count} hosting request(s).", messages.SUCCESS)

    @admin.action(description=gettext_lazy("Approve and create the space for selected requests"))
    def approve_and_create_selected(self, request, queryset):
        from apps.hosting_requests import provision
        rows = list(queryset)
        if "confirm_decision" not in request.POST:
            return self._confirm(request, rows, action_name="approve_and_create_selected", needs_reason=False,
                                 title="Approve and create spaces", submit_label="Approve and create")
        self._decide(request, rows, lambda row: provision.approve_and_create(request.user, row.pk),
                     "Approved and created a space for")

    @admin.action(description=gettext_lazy("Accept selected hosting requests"))
    def accept_selected(self, request, queryset):
        rows = list(queryset)
        if "confirm_decision" not in request.POST:
            return self._confirm(request, rows, action_name="accept_selected", needs_reason=False,
                                 title="Accept hosting requests", submit_label="Accept requests")
        self._decide(request, rows, lambda row: workflow.accept(request.user, row.pk), "Accepted")

    @admin.action(description=gettext_lazy("Reject selected hosting requests"))
    def reject_selected(self, request, queryset):
        rows = list(queryset)
        if "confirm_decision" not in request.POST:
            return self._confirm(request, rows, action_name="reject_selected", needs_reason=True,
                                 title="Reject hosting requests", submit_label="Reject requests")
        reason = request.POST.get("rejection_reason", "")
        self._decide(request, rows, lambda row: workflow.reject(request.user, row.pk, reason), "Rejected")

    @admin.action(description=gettext_lazy("Request changes on selected hosting requests"))
    def request_changes_selected(self, request, queryset):
        rows = list(queryset)
        if "confirm_decision" not in request.POST:
            return self._confirm(request, rows, action_name="request_changes_selected", needs_reason=True,
                                 title="Request changes", submit_label="Send the request for changes",
                                 reason_label="What should the applicant change?")
        note = request.POST.get("rejection_reason", "")
        self._decide(request, rows, lambda row: workflow.request_changes(request.user, row.pk, note),
                     "Asked for changes on")
