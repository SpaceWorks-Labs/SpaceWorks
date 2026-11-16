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


@admin.register(ApiClientImportApproval)
class ApiClientImportApprovalAdmin(SuperuserOnlyModelAdmin, ModelAdmin):
    list_display = ("source_client_ref", "makerspace", "api_client", "approved_at")
    readonly_fields = tuple(field.name for field in ApiClientImportApproval._meta.fields)

    def has_add_permission(self, request):
        return False

    def has_delete_permission(self, request, obj=None):
        return False
