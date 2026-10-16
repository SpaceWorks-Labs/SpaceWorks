from django import forms
from django.contrib import admin
from unfold.admin import ModelAdmin

from apps.accounts.login_methods_validation import validate_login_methods
from apps.accounts.models_login_methods import PlatformLoginMethods
from apps.accounts.models_oidc import OidcProvider
from apps.accounts.models_oidc_browser import OidcBrowserAttempt
from apps.accounts.models_social import PlatformSocialAuthSettings, SocialIdentity
from apps.accounts.social_lockout import CONFIG_FIELDS, disabling_lockout_message
from config.admin_access import SuperuserOnlyModelAdmin
from config.admin_audit import AuditedControlChangeMixin


class PlatformSocialAuthSettingsForm(forms.ModelForm):
    github_client_secret_raw = forms.CharField(
        required=False, widget=forms.PasswordInput(render_value=False),
        help_text="Write-only. Leave blank to keep the current encrypted GitHub secret.",
    )
    clear_github_client_secret = forms.BooleanField(required=False)
    apple_private_key_raw = forms.CharField(
        required=False,
        widget=forms.PasswordInput(render_value=False),
        help_text="Write-only. Leave blank to keep the current encrypted Apple key.",
    )

    class Meta:
        model = PlatformSocialAuthSettings
        exclude = ("apple_private_key", "github_client_secret")

    def clean(self):
        # Turning a provider OFF is the dangerous direction: accounts created through it
        # that never set a password have no other way in, and forgot-password cannot
        # help them (there is no usable password to reset). Checked here rather than in
        # the model so the superadmin sees it as a form error with the remedy attached.
        cleaned = super().clean()
        stored = PlatformSocialAuthSettings.objects.filter(pk=1).first()
        incoming = PlatformSocialAuthSettings(
            **{
                field: cleaned.get(field, getattr(stored, field, "") if stored else "")
                for field in CONFIG_FIELDS
            }
        )
        if cleaned.get("clear_github_client_secret"):
            incoming.github_client_secret = ""
        elif cleaned.get("github_client_secret_raw"):
            incoming.set_github_client_secret(cleaned["github_client_secret_raw"])
        message = disabling_lockout_message(stored, incoming)
        if message:
            raise forms.ValidationError(message)
        return cleaned

    def save(self, commit=True):
        row = super().save(commit=False)
        if self.cleaned_data.get("apple_private_key_raw"):
            row.set_apple_private_key(self.cleaned_data["apple_private_key_raw"])
        if self.cleaned_data.get("clear_github_client_secret"):
            row.set_github_client_secret("")
        elif self.cleaned_data.get("github_client_secret_raw"):
            row.set_github_client_secret(self.cleaned_data["github_client_secret_raw"])
        if commit:
            row.save()
            from apps.accounts.social_csp import clear_social_csp_cache

            clear_social_csp_cache()
        return row


@admin.register(PlatformSocialAuthSettings)
class PlatformSocialAuthSettingsAdmin(AuditedControlChangeMixin, SuperuserOnlyModelAdmin, ModelAdmin):
    audit_action = "platform.social_auth_settings_updated"
    form = PlatformSocialAuthSettingsForm

    def has_add_permission(self, request):
        return not PlatformSocialAuthSettings.objects.exists()


class PlatformLoginMethodsForm(forms.ModelForm):
    class Meta:
        model = PlatformLoginMethods
        fields = "__all__"

    def clean(self):
        cleaned = super().clean()
        proposed = PlatformLoginMethods()
        for field in proposed._meta.fields:
            if field.name in cleaned:
                setattr(proposed, field.name, cleaned[field.name])
            elif self.instance is not None:
                setattr(proposed, field.name, getattr(self.instance, field.name))
        stored = PlatformLoginMethods.objects.filter(pk=self.instance.pk).first() if self.instance.pk else None
        validate_login_methods(proposed, current=stored)
        return cleaned


@admin.register(PlatformLoginMethods)
class PlatformLoginMethodsAdmin(AuditedControlChangeMixin, SuperuserOnlyModelAdmin, ModelAdmin):
    audit_action = "platform.login_methods_updated"
    """Which ways in this deployment offers. Platform-scoped, never a tenant feature."""

    readonly_fields = ("mfa_enabled", "google_enabled", "apple_enabled", "github_enabled")
    form = PlatformLoginMethodsForm
    list_display = (
        "__str__", "password_enabled", "social_enabled", "phone_enabled",
        "self_registration_enabled", "mfa_enabled",
    )
    fieldsets = (
        ("Sign-in methods", {"fields": (
            "password_enabled", "social_enabled", "phone_enabled", "self_registration_enabled",
        )}),
        ("Installed providers", {"fields": ("google_enabled", "apple_enabled", "github_enabled")}),
        ("Two-step sign-in", {"fields": ("mfa_enabled",)}),
    )

    def has_add_permission(self, request):
        return not PlatformLoginMethods.objects.exists()

    def has_delete_permission(self, request, obj=None):
        """Deleting the row would silently re-enable every method.

        `load()` reads an absent row as "nothing configured", which is every switch on —
        correct for a deployment that has never touched them, and a surprise for one that
        deliberately turned two off.
        """
        return False


@admin.register(SocialIdentity)
class SocialIdentityAdmin(SuperuserOnlyModelAdmin, ModelAdmin):
    list_display = ("id", "user", "provider", "created_at")
    readonly_fields = ("user", "provider", "provider_sub", "created_at", "updated_at")

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False


@admin.register(OidcProvider)
class OidcProviderAdmin(AuditedControlChangeMixin, SuperuserOnlyModelAdmin, ModelAdmin):
    audit_action = "platform.oidc_provider_saved"
    """Deployment-configured OpenID Connect providers.

    Superadmin-only and platform-scoped, like the built-in providers and for the same
    reason: identity resolves before a makerspace is selected, so a per-tenant provider
    would be unreachable at token-verification time.
    """

    list_display = ("display_name", "slug", "issuer", "is_enabled", "allow_auto_link")
    list_filter = ("is_enabled", "allow_auto_link")
    search_fields = ("slug", "display_name", "issuer")
    readonly_fields = ("created_at", "updated_at")

    def has_delete_permission(self, request, obj=None):
        """Deleting the provider row would orphan every SocialIdentity that names it.

        Those users would keep a stored identity pointing at a provider the deployment
        can no longer resolve, and any who never set a password could not recover --
        the same lockout `social_lockout` refuses for the built-ins. Disable it instead:
        the row stays, the login stops, and re-enabling restores it.
        """
        return False


@admin.register(OidcBrowserAttempt)
class OidcBrowserAttemptAdmin(SuperuserOnlyModelAdmin, ModelAdmin):
    list_display = ("id", "provider", "created_at", "expires_at", "consumed_at")
    list_filter = ("provider", "consumed_at")
    fields = (
        "provider",
        "intended_user",
        "intended_membership",
        "created_at",
        "expires_at",
        "consumed_at",
    )
    readonly_fields = fields

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False
