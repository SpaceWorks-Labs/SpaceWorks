from django import forms
from django.contrib import admin
from unfold.admin import ModelAdmin

from apps.integrations.models_sms import DailyOtpSmsCounter, PlatformSmsSettings
from config.admin_access import SuperuserOnlyModelAdmin
from config.admin_audit import AuditedControlChangeMixin


class PlatformSmsSettingsForm(forms.ModelForm):
    auth_token_raw = forms.CharField(
        required=False,
        widget=forms.PasswordInput(render_value=False),
        label="Auth token",
        help_text="Write-only. Leave blank to keep the current encrypted token.",
    )
    clear_auth_token = forms.BooleanField(required=False)

    class Meta:
        model = PlatformSmsSettings
        fields = ("is_enabled", "provider", "account_sid", "from_number", "notifications_enabled", "notifications_from_number")

    def clean_from_number(self):
        """Validate the sender at the form, not at send time.

        A malformed sender makes every text fail at the vendor with nothing surfaced to
        the operator -- phone login would simply appear broken.
        """
        value = (self.cleaned_data.get("from_number") or "").strip()
        if not value:
            return value
        from apps.accounts.phone_numbers import InvalidPhoneNumber, normalize_e164

        try:
            return normalize_e164(value)
        except InvalidPhoneNumber as exc:
            raise forms.ValidationError(str(exc)) from exc

    def clean_notifications_from_number(self):
        value = (self.cleaned_data.get("notifications_from_number") or "").strip()
        if not value:
            return value
        from apps.accounts.phone_numbers import InvalidPhoneNumber, normalize_e164
        try:
            return normalize_e164(value)
        except InvalidPhoneNumber as exc:
            raise forms.ValidationError(str(exc)) from exc

    def clean(self):
        values = super().clean()
        from types import SimpleNamespace
        from rest_framework.exceptions import ValidationError
        from apps.integrations.messaging.settings_service import validate_platform_sms
        try:
            validate_platform_sms(SimpleNamespace(**{key: values.get(key, "") for key in (
                "account_sid", "from_number", "notifications_from_number",
            )}))
        except ValidationError as exc:
            raise forms.ValidationError(str(exc.detail)) from exc
        if not values.get("auth_token_raw") and not values.get("clear_auth_token"):
            try:
                self.instance.get_auth_token()
            except Exception:
                self.add_error("auth_token_raw", "Re-enter or clear the unreadable credential.")
        return values

    def save(self, commit=True):
        row = super().save(commit=False)
        if self.cleaned_data.get("clear_auth_token"):
            row.set_auth_token("")
        elif self.cleaned_data.get("auth_token_raw"):
            row.set_auth_token(self.cleaned_data["auth_token_raw"])
        if commit:
            from apps.integrations.messaging.settings_service import sync_platform_sms
            sync_platform_sms(row)
        return row


@admin.register(PlatformSmsSettings)
class PlatformSmsSettingsAdmin(AuditedControlChangeMixin, SuperuserOnlyModelAdmin, ModelAdmin):
    audit_action = "platform.sms_settings_updated"
    form = PlatformSmsSettingsForm
    fieldsets = (
        (
            None,
            {
                "fields": (
                    "is_enabled",
                    "provider",
                    "account_sid",
                    "auth_token_raw",
                    "clear_auth_token",
                    "from_number",
                    "notifications_enabled",
                    "notifications_from_number",
                ),
                "description": (
                    "Platform-wide SMS for sign-in codes. Phone sign-in stays hidden "
                    "from the login screen until this is enabled and complete."
                ),
            },
        ),
    )
    list_display = ("__str__", "is_enabled", "provider", "updated_at")

    def save_model(self, request, obj, form, change):
        from apps.integrations.messaging.settings_service import sync_platform_sms
        sync_platform_sms(obj)
        super().save_model(request, obj, form, change)

    def has_add_permission(self, request):
        # Singleton at pk=1, same as the email and push settings rows.
        return not PlatformSmsSettings.objects.exists()

    def has_delete_permission(self, request, obj=None):
        return False


@admin.register(DailyOtpSmsCounter)
class DailyOtpSmsCounterAdmin(SuperuserOnlyModelAdmin, ModelAdmin):
    list_display = ("day", "count")
    ordering = ("-day",)

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False
