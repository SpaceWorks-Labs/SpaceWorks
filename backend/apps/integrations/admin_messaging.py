"""Operator-owned WhatsApp credentials and platform templates only."""
from django import forms
from django.contrib import admin
from rest_framework.exceptions import ValidationError as ApiValidationError
from unfold.admin import ModelAdmin

from apps.integrations.models import MakerspaceMessagingSettings, PlatformWhatsAppSettings, WhatsAppTemplateBinding
from apps.integrations.messaging.settings_service import sync_platform_whatsapp
from apps.integrations.messaging.templates import WHATSAPP_LANGUAGES, validate_binding
from config.admin_access import SuperuserOnlyModelAdmin
from config.admin_audit import AuditedControlChangeMixin


class PlatformWhatsAppSettingsForm(forms.ModelForm):
    access_token_raw = forms.CharField(required=False, widget=forms.PasswordInput(render_value=False))
    app_secret_raw = forms.CharField(required=False, widget=forms.PasswordInput(render_value=False))
    clear_access_token = forms.BooleanField(required=False)
    clear_app_secret = forms.BooleanField(required=False)

    class Meta:
        model = PlatformWhatsAppSettings
        fields = ("is_enabled", "app_id", "phone_number_id", "business_account_id")

    def clean(self):
        cleaned = super().clean()
        for key in ("app_id", "phone_number_id", "business_account_id"):
            value = cleaned.get(key, "")
            if value and (not value.isascii() or not value.isdigit()):
                self.add_error(key, "Enter the numeric Meta identifier.")
        for key in ("access_token", "app_secret"):
            if not cleaned.get(key + "_raw") and not cleaned.get("clear_" + key):
                try:
                    self.instance.get_secret(key)
                except Exception:
                    self.add_error(key + "_raw", "Re-enter or clear the unreadable credential.")
        from apps.integrations.messaging.resolver import sender_key
        key = sender_key("whatsapp", business_account_id=cleaned.get("business_account_id", ""),
                         phone_number_id=cleaned.get("phone_number_id", ""))
        if key and MakerspaceMessagingSettings.objects.filter(whatsapp_sender_key=key).exists():
            raise forms.ValidationError("This sender is reserved by another configuration.")
        return cleaned

    def save(self, commit=True):
        row = super().save(commit=False)
        for key in ("access_token", "app_secret"):
            if self.cleaned_data.get("clear_" + key):
                row.set_secret(key, "")
            elif self.cleaned_data.get(key + "_raw"):
                row.set_secret(key, self.cleaned_data[key + "_raw"])
        if commit:
            sync_platform_whatsapp(row)
        return row


@admin.register(PlatformWhatsAppSettings)
class PlatformWhatsAppSettingsAdmin(AuditedControlChangeMixin, SuperuserOnlyModelAdmin, ModelAdmin):
    audit_action = "platform.whatsapp_settings_updated"
    form = PlatformWhatsAppSettingsForm
    fields = ("is_enabled", "app_id", "phone_number_id", "business_account_id", "access_token_raw", "clear_access_token",
              "app_secret_raw", "clear_app_secret", "webhook_verify_token", "callback_url", "updated_at")
    readonly_fields = ("webhook_verify_token", "callback_url", "updated_at")

    @admin.display(description="Webhook callback")
    def callback_url(self, obj):
        from apps.integrations.messaging.resolver import webhook_urls
        return webhook_urls("whatsapp")["callback"]

    def save_model(self, request, obj, form, change):
        sync_platform_whatsapp(obj)
        super().save_model(request, obj, form, change)

    def has_add_permission(self, request):
        return super().has_add_permission(request) and not PlatformWhatsAppSettings.objects.exists()

    def has_delete_permission(self, request, obj=None):
        return False


class PlatformTemplateBindingForm(forms.ModelForm):
    language = forms.ChoiceField(choices=[(code, code) for code in WHATSAPP_LANGUAGES])
    components = forms.JSONField(required=False, help_text="Optional Meta component metadata. Only positional text BODY is supported.")

    class Meta:
        model = WhatsAppTemplateBinding
        fields = ("feature", "event", "audience", "template_name", "language", "parameters", "is_active")

    def clean(self):
        values = super().clean()
        if self.errors:
            return values
        candidate = dict(values)
        if candidate.get("components") is None:
            candidate.pop("components", None)
        try:
            validate_binding(candidate, self.instance)
        except ApiValidationError as exc:
            raise forms.ValidationError(str(exc.detail)) from exc
        platform = PlatformWhatsAppSettings.objects.filter(pk=1).first()
        if not platform or not platform.business_account_id:
            raise forms.ValidationError("Configure the platform WhatsApp business account first.")
        from apps.integrations.messaging.templates_provider import validate_provider_template, TemplateCheckUnavailable
        try:
            validate_provider_template(business_account_id=platform.business_account_id,
                access_token=platform.get_secret("access_token"), template_name=values["template_name"],
                language=values["language"], parameters=values["parameters"])
        except (ApiValidationError, TemplateCheckUnavailable) as exc:
            raise forms.ValidationError(str(exc.detail)) from exc
        self.instance.business_account_id = platform.business_account_id
        self.instance.makerspace = None
        self.instance.needs_review = False
        if WhatsAppTemplateBinding.objects.filter(makerspace__isnull=True, feature=values["feature"],
            event=values["event"], audience=values["audience"]).exclude(pk=self.instance.pk).exists():
            raise forms.ValidationError("This event and audience already has a platform binding.")
        return values


@admin.register(WhatsAppTemplateBinding)
class PlatformTemplateBindingAdmin(AuditedControlChangeMixin, SuperuserOnlyModelAdmin, ModelAdmin):
    audit_action = "platform.whatsapp_template_updated"
    form = PlatformTemplateBindingForm
    fields = ("feature", "event", "audience", "template_name", "language", "parameters", "components", "is_active")
    list_display = ("feature", "event", "audience", "template_name", "language", "needs_review")

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def get_queryset(self, request):
        return super().get_queryset(request).filter(makerspace__isnull=True)

    def has_delete_permission(self, request, obj=None):
        # Deactivation preserves audited history; API tenant DELETE has its own audit.
        return False
