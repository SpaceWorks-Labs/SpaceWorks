"""Safe control-plane form; I mounts this in the existing audited ModelAdmin."""

from django.utils.translation import gettext
from django import forms
from rest_framework.exceptions import ValidationError as ApiValidationError

from .email_provider_serializers import apply_provider_update, validate_provider_update
from .models_email import PlatformEmailSettings


class PlatformEmailProviderForm(forms.ModelForm):
    provider_credentials = forms.JSONField(required=False, widget=forms.Textarea,
        help_text="Write-only JSON. Leave blank to keep current credentials.")

    class Meta:
        model = PlatformEmailSettings
        exclude = ("smtp_password", "email_provider_config")

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._original_provider = self.instance.email_provider

    def clean(self):
        cleaned = super().clean()
        values = dict(cleaned)
        credentials = values.pop("provider_credentials", None)
        if credentials is not None:
            values["email_provider_config"] = credentials
        try:
            validate_provider_update(values, self.instance)
        except ApiValidationError as exc:
            detail = exc.detail if isinstance(exc.detail, dict) else {}
            # SMTP endpoint errors stay on their form field; provider errors stay generic.
            fields = {key: value if isinstance(value, list) else [value]
                      for key, value in detail.items() if key in self.fields}
            raise forms.ValidationError(
                fields or gettext("Check the selected email provider and required fields.")) from None
        return cleaned

    def save(self, commit=True):
        instance = super().save(commit=False)
        credentials = self.cleaned_data.get("provider_credentials")
        if credentials is not None:
            apply_provider_update(instance, {"email_provider_config": credentials})
        elif instance.email_provider != self._original_provider:
            instance.set_email_provider_config({})
        if commit:
            instance.save()
            self.save_m2m()
        return instance
