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
from django.utils.translation import gettext_lazy


@admin.register(ApiClient)
class ApiClientAdmin(RecentReauthenticationAdminMixin, SuperuserOnlyModelAdmin, ModelAdmin):
    form = ApiClientAdminForm
    search_fields = ("label", "client_id", "makerspace__name")
    list_display = (
        "label",
        "client_id",
        "makerspace",
        "makerspace_public_code",
        "is_active",
        "last_seen_at",
        "last_seen_ip",
        "created_at",
    )
    list_filter = ("is_active", "makerspace")
    readonly_fields = (
        "client_id",
        "makerspace_public_code",
        "makerspace_public_api_key",
        "created_by",
        "last_seen_at",
        "last_seen_ip",
        "created_at",
        "updated_at",
    )
    fields = (
        "label",
        "makerspace",
        "allowed_origins",
        "is_active",
        "telegram_group_chat_id",
        "telegram_bot_token",
        "smtp_host",
        "smtp_port",
        "smtp_username",
        "smtp_password",
        "smtp_use_tls",
        "smtp_use_ssl",
        "smtp_from_email",
        "client_id",
        "makerspace_public_code",
        "makerspace_public_api_key",
        "created_by",
        "last_seen_at",
        "last_seen_ip",
        "created_at",
        "updated_at",
    )

    # Generate + reveal the secret once at creation.
    def save_model(self, request, obj, form, change):
        new_secret = None
        if not change:
            obj.created_by = request.user
            new_secret = secrets.token_urlsafe(32)
            obj.set_secret(new_secret)
        super().save_model(request, obj, form, change)
        # Literal actions keep both rows presentable (a conditional action is denied).
        if change:
            audit.record(request.user, "api_client.updated",
                         makerspace=obj.makerspace, target=obj, meta={"surface": "control"})
        else:
            audit.record(request.user, "api_client.created",
                         makerspace=obj.makerspace, target=obj, meta={"surface": "control"})
        self._save_makerspace_settings(obj, form)
        sync_makerspace_origins(obj.makerspace)
        if new_secret:
            messages.warning(
                request,
                f"Client secret for {obj.client_id} (shown once - copy it now): {new_secret}",
            )

    def delete_model(self, request, obj):
        makerspace = obj.makerspace
        audit.record(request.user, "api_client.deleted", makerspace=makerspace, target=obj, meta={"surface": "control"})
        super().delete_model(request, obj)
        sync_makerspace_origins(makerspace)

    def delete_queryset(self, request, queryset):
        makerspaces = list({client.makerspace for client in queryset.select_related("makerspace")})
        for obj in queryset:
            audit.record(request.user, "api_client.deleted", makerspace=obj.makerspace, target=obj, meta={"surface": "control"})
        super().delete_queryset(request, queryset)
        for makerspace in makerspaces:
            sync_makerspace_origins(makerspace)

    def _save_makerspace_settings(self, obj, form):
        if not obj.makerspace_id:
            return
        makerspace = obj.makerspace
        text_fields = [
            "telegram_group_chat_id",
            "smtp_host",
            "smtp_username",
            "smtp_from_email",
        ]
        for field in text_fields:
            setattr(makerspace, field, form.cleaned_data.get(field) or "")
        if form.cleaned_data.get("telegram_bot_token"):
            makerspace.set_telegram_bot_token(form.cleaned_data["telegram_bot_token"])
        if form.cleaned_data.get("smtp_password"):
            makerspace.set_smtp_password(form.cleaned_data["smtp_password"])
        makerspace.smtp_port = form.cleaned_data.get("smtp_port") or 587
        makerspace.smtp_use_tls = bool(form.cleaned_data.get("smtp_use_tls"))
        makerspace.smtp_use_ssl = bool(form.cleaned_data.get("smtp_use_ssl"))
        makerspace.save(
            update_fields=[
                *text_fields,
                "telegram_bot_token",
                "smtp_password",
                "smtp_port",
                "smtp_use_tls",
                "smtp_use_ssl",
                "updated_at",
            ]
        )

    @admin.display(description=gettext_lazy("Makerspace code"))
    def makerspace_public_code(self, obj):
        return obj.makerspace.public_code if obj.makerspace_id else "-"

    @admin.display(description=gettext_lazy("Legacy public API key"))
    def makerspace_public_api_key(self, obj):
        return obj.makerspace.public_api_key if obj.makerspace_id else "-"


