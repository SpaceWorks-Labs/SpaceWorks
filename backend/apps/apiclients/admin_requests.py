from django.contrib import admin, messages
from django.core.exceptions import ValidationError as DjangoValidationError
from rest_framework.exceptions import ValidationError as DRFValidationError
from unfold.admin import ModelAdmin

from apps.apiclients import key_request_decisions
from apps.apiclients.models import ApiKeyRequest
from config.admin_access import SuperuserOnlyModelAdmin



from apps.accounts.reauthentication_control import RecentReauthenticationAdminMixin
from django.utils.translation import gettext_lazy


@admin.register(ApiKeyRequest)
class ApiKeyRequestAdmin(RecentReauthenticationAdminMixin, SuperuserOnlyModelAdmin, ModelAdmin):
    actions = ["approve_and_issue", "reject_selected"]
    list_display = ("label", "makerspace", "requester", "status", "created_at")
    list_filter = ("status", "makerspace")
    readonly_fields = (
        "requester",
        "created_at",
        "updated_at",
        "resolved_by",
        "resolved_at",
    )
    search_fields = ("label",)

    @admin.action(description=gettext_lazy("Approve selected API key requests and issue clients"))
    def approve_and_issue(self, request, queryset):
        approved_count = skipped_count = 0
        for api_key_request in queryset.select_related("makerspace", "requester"):
            if api_key_request.status != ApiKeyRequest.Status.PENDING:
                skipped_count += 1
                continue
            try:
                _row, client, raw_secret = key_request_decisions.approve(request.user, api_key_request)
            except DRFValidationError as exc:
                self.message_user(request, f"{api_key_request.pk}: {exc.detail}", level=messages.ERROR)
                continue
            except DjangoValidationError as exc:
                self.message_user(request, f"{api_key_request.pk}: {getattr(exc, 'message_dict', exc.messages)}",
                                  level=messages.ERROR)
                continue
            self.message_user(request, f"Client secret for {client.client_id} (shown once - copy it now): {raw_secret}",
                              level=messages.WARNING)
            approved_count += 1
        if approved_count:
            self.message_user(request, f"Approved {approved_count} API key request(s).", level=messages.SUCCESS)
        if skipped_count:
            self.message_user(request, f"Skipped {skipped_count} non-pending API key request(s).",
                              level=messages.WARNING)

    @admin.action(description=gettext_lazy("Reject selected API key requests"))
    def reject_selected(self, request, queryset):
        rejected_count = skipped_count = 0
        for api_key_request in queryset.select_related("makerspace", "requester"):
            if api_key_request.status != ApiKeyRequest.Status.PENDING:
                skipped_count += 1
                continue
            try:
                key_request_decisions.reject(request.user, api_key_request)
            except DjangoValidationError:
                skipped_count += 1  # decided meanwhile
                continue
            rejected_count += 1
        if rejected_count:
            self.message_user(request, f"Rejected {rejected_count} API key request(s).", level=messages.SUCCESS)
        if skipped_count:
            self.message_user(request, f"Skipped {skipped_count} non-pending API key request(s).",
                              level=messages.WARNING)
