from django.contrib import admin
from django.http import Http404
from unfold.admin import ModelAdmin

from apps.accounts.models_password_reset import PasswordResetEnvelope
from config.admin_access import SuperuserOnlyModelAdmin


@admin.register(PasswordResetEnvelope)
class PasswordResetEnvelopeAdmin(SuperuserOnlyModelAdmin, ModelAdmin):
    """Operational visibility without exposing digests or writable workflow state."""

    list_display = (
        "email_normalized",
        "status",
        "generation",
        "requested_at",
        "terminal_at",
    )
    list_filter = ("status",)
    search_fields = ("email_normalized", "email_fingerprint", "claim_owner")
    fields = (
        "email_normalized",
        "email_fingerprint",
        "user",
        "status",
        "attempts",
        "generation",
        "requested_at",
        "expires_at",
        "consumed_at",
        "claimed_at",
        "claim_owner",
        "claim_expires_at",
        "superseded_at",
        "terminal_at",
    )
    readonly_fields = fields

    def get_queryset(self, request):
        from apps.accounts.staff_identity import shell_q

        # One account per person: an inert shell's envelopes are history, never listed.
        return super().get_queryset(request).exclude(shell_q("user__"))

    def _obj_in_hidden(self, obj):
        from config.admin_account_scope import staff_account_hidden

        return bool(obj is not None and staff_account_hidden(obj.user)) or super()._obj_in_hidden(obj)

    def get_object(self, request, object_id, from_field=None):
        obj = super().get_object(request, object_id, from_field)
        if obj is None or self._obj_in_hidden(obj):
            raise Http404
        return obj

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False
