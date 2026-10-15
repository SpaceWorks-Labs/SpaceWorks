import secrets

from django.contrib import admin, messages
from django.core.exceptions import ValidationError as DjangoValidationError
from django.db import transaction
from django.utils import timezone
from rest_framework.exceptions import ValidationError as DRFValidationError
from unfold.admin import ModelAdmin

from apps.apiclients.admin_forms import ApiClientAdminForm
from apps.apiclients.models import ApiClient, ApiClientImportApproval, ApiKeyRequest
from apps.apiclients.notifications import notify_api_key_request_resolved
from apps.apiclients.scope_registry import LEGACY_SCOPE
from apps.apiclients.services import sync_makerspace_origins
from apps.audit import services as audit
from apps.makerspaces import limits
from config.admin_access import SuperuserOnlyModelAdmin



from apps.accounts.reauthentication_control import RecentReauthenticationAdminMixin


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

    @admin.action(description="Approve selected API key requests and issue clients")
    def approve_and_issue(self, request, queryset):
        approved_count = 0
        skipped_count = 0
        for api_key_request in queryset.select_related("makerspace", "requester"):
            if api_key_request.status != ApiKeyRequest.Status.PENDING:
                skipped_count += 1
                continue

            try:
                with transaction.atomic():
                    limits.check_quota(
                        api_key_request.makerspace,
                        "api_clients",
                        adding=1,
                    )
                    client, raw_secret = ApiClient.issue(
                        label=api_key_request.label,
                        makerspace=api_key_request.makerspace,
                        allowed_origins=api_key_request.allowed_origins or [],
                        created_by=request.user,
                        client_type="server",
                        scopes=[LEGACY_SCOPE],
                    )
            except DRFValidationError as exc:
                self.message_user(
                    request,
                    f"{api_key_request.pk}: {exc.detail}",
                    level=messages.ERROR,
                )
                continue
            except DjangoValidationError as exc:
                self.message_user(
                    request,
                    (
                        f"{api_key_request.pk}: "
                        f"{getattr(exc, 'message_dict', exc.messages)}"
                    ),
                    level=messages.ERROR,
                )
                continue
            sync_makerspace_origins(api_key_request.makerspace)
            api_key_request.status = ApiKeyRequest.Status.APPROVED
            api_key_request.resolved_by = request.user
            api_key_request.resolved_at = timezone.now()
            api_key_request.save(
                update_fields=[
                    "status",
                    "resolved_by",
                    "resolved_at",
                    "updated_at",
                ]
            )
            audit.record(
                request.user,
                "api_key_request.approved",
                makerspace=api_key_request.makerspace,
                target=api_key_request,
                meta={"api_client_id": client.pk},
            )
            audit.record(
                request.user,
                "api_client.created",
                makerspace=client.makerspace,
                target=client,
                meta={
                    "allowed_origins": client.allowed_origins,
                    "api_key_request_id": api_key_request.pk,
                },
            )
            self.message_user(
                request,
                (
                    f"Client secret for {client.client_id} "
                    f"(shown once - copy it now): {raw_secret}"
                ),
                level=messages.WARNING,
            )
            notify_api_key_request_resolved(api_key_request)
            approved_count += 1

        if approved_count:
            self.message_user(
                request,
                f"Approved {approved_count} API key request(s).",
                level=messages.SUCCESS,
            )
        if skipped_count:
            self.message_user(
                request,
                f"Skipped {skipped_count} non-pending API key request(s).",
                level=messages.WARNING,
            )
    @admin.action(description="Reject selected API key requests")
    def reject_selected(self, request, queryset):
        rejected_count = 0
        skipped_count = 0
        for api_key_request in queryset.select_related("makerspace", "requester"):
            if api_key_request.status != ApiKeyRequest.Status.PENDING:
                skipped_count += 1
                continue

            api_key_request.status = ApiKeyRequest.Status.REJECTED
            api_key_request.resolved_by = request.user
            api_key_request.resolved_at = timezone.now()
            api_key_request.save(
                update_fields=[
                    "status",
                    "resolved_by",
                    "resolved_at",
                    "updated_at",
                ]
            )
            audit.record(
                request.user,
                "api_key_request.rejected",
                makerspace=api_key_request.makerspace,
                target=api_key_request,
            )
            notify_api_key_request_resolved(api_key_request)
            rejected_count += 1

        if rejected_count:
            self.message_user(
                request,
                f"Rejected {rejected_count} API key request(s).",
                level=messages.SUCCESS,
            )
        if skipped_count:
            self.message_user(
                request,
                f"Skipped {skipped_count} non-pending API key request(s).",
                level=messages.WARNING,
            )


