import json

from cryptography.hazmat.primitives import serialization
from cryptography.exceptions import UnsupportedAlgorithm
from cryptography.hazmat.primitives.asymmetric import rsa
from django import forms
from django.contrib import admin
from unfold.admin import ModelAdmin

from apps.accounts.models_attestation import PlatformAttestationSettings
from config.admin_access import SuperuserOnlyModelAdmin
from config.admin_audit import AuditedControlChangeMixin


class PlatformAttestationSettingsForm(forms.ModelForm):
    play_integrity_service_account_raw = forms.CharField(
        required=False, widget=forms.PasswordInput(render_value=False),
        help_text="Write-only service-account JSON. Leave blank to keep the encrypted credential.",
    )
    clear_play_integrity_credentials = forms.BooleanField(required=False)

    class Meta:
        model = PlatformAttestationSettings
        fields = ("app_display_name",)

    def clean_play_integrity_service_account_raw(self):
        raw = self.cleaned_data["play_integrity_service_account_raw"]
        if raw:
            try:
                account = json.loads(raw)
                if account.get("type") != "service_account" or not account.get("client_email"):
                    raise ValueError("Invalid account")
                key = serialization.load_pem_private_key(account["private_key"].encode(), password=None)
                if not isinstance(key, rsa.RSAPrivateKey):
                    raise ValueError("RSA key required")
            except (KeyError, ValueError, TypeError, AttributeError, UnsupportedAlgorithm) as exc:
                raise forms.ValidationError("Enter a Google service-account JSON with an RSA private key.") from exc
        return raw

    def save(self, commit=True):
        row = super().save(commit=False)
        if self.cleaned_data.get("clear_play_integrity_credentials"):
            row.set_play_integrity_service_account("")
        elif self.cleaned_data.get("play_integrity_service_account_raw"):
            row.set_play_integrity_service_account(self.cleaned_data["play_integrity_service_account_raw"])
        if commit:
            row.save()
        return row


@admin.register(PlatformAttestationSettings)
class PlatformAttestationSettingsAdmin(AuditedControlChangeMixin, SuperuserOnlyModelAdmin, ModelAdmin):
    audit_action = "platform.attestation_settings_updated"
    form = PlatformAttestationSettingsForm
    fields = ("app_display_name", "play_integrity_service_account_raw", "clear_play_integrity_credentials", "updated_at")
    readonly_fields = ("updated_at",)

    def has_add_permission(self, request):
        return super().has_add_permission(request) and not PlatformAttestationSettings.objects.exists()

    def has_delete_permission(self, request, obj=None):
        return False
