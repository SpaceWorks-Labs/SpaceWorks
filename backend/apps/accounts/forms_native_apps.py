"""Validate public app identity inputs at the control-plane boundary."""

from django.utils.translation import gettext
import re

from django import forms
from django.core.exceptions import ValidationError

from apps.accounts.models_devices import NativeAppRegistration
from apps.accounts.native_app_identity import (
    ANDROID_PACKAGE, APPLE_BUNDLE, VERSION_PATTERN, normalise_signing_identities,
)


class NativeAppRegistrationForm(forms.ModelForm):
    signing_identities = forms.JSONField(
        label="Distribution signer digests / App ID Prefix",
        help_text="JSON list: Android SHA-256 distribution digests (1–5, hex or colon-hex); Apple exactly one App ID Prefix (usually Team ID). Never the Android upload key.",
    )

    class Meta:
        model = NativeAppRegistration
        fields = "__all__"

    def clean(self):
        data = super().clean()
        platform = data.get("platform")
        app_id = data.get("app_id")
        pattern = ANDROID_PACKAGE if platform == "android" else APPLE_BUNDLE
        if app_id and not re.fullmatch(pattern, app_id):
            self.add_error("app_id", "Enter a valid dotted Android package name or Apple bundle ID.")
        if "signing_identities" in data and platform:
            try:
                data["signing_identities"] = normalise_signing_identities(platform, data["signing_identities"])
            except ValidationError as exc:
                self.add_error("signing_identities", exc)
        return data

    def clean_min_supported_version(self):
        value = self.cleaned_data.get("min_supported_version")
        if value and not re.fullmatch(VERSION_PATTERN, value):
            raise forms.ValidationError(gettext("Enter a dotted numeric version such as 1.4.0, or leave blank."))
        return value or None
