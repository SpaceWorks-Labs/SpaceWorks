from .email_provider_forms import PlatformEmailProviderForm
from django.contrib import admin

from config.admin_access import SuperuserOnlyModelAdmin
from config.admin_audit import AuditedControlChangeMixin

from apps.integrations import admin_email_templates  # noqa: F401
from apps.integrations import admin_destinations  # noqa: F401
from apps.integrations import admin_email_logs  # noqa: F401
from apps.integrations import admin_notification_mutes  # noqa: F401
from apps.integrations import admin_notifications  # noqa: F401
from apps.integrations import admin_push  # noqa: F401
from apps.integrations import admin_recipients  # noqa: F401
from apps.integrations import admin_sms  # noqa: F401
from apps.integrations import admin_suppression  # noqa: F401
from apps.integrations.models import PlatformEmailSettings
from apps.integrations.smtp_validation import validate_smtp_settings

# Public name kept from before the provider-aware form replaced the SMTP-only one.
PlatformEmailSettingsAdminForm = PlatformEmailProviderForm

@admin.register(PlatformEmailSettings)
class PlatformEmailSettingsAdmin(AuditedControlChangeMixin, SuperuserOnlyModelAdmin, admin.ModelAdmin):
    audit_action = "platform.email_settings_updated"
    form = PlatformEmailSettingsAdminForm
    list_display = ("smtp_host", "smtp_port", "from_email", "updated_at")
    # smtp_password holds the Fernet-encrypted value; never edit it as raw ciphertext
    # in the admin. The React superadmin Platform Email panel is the write surface.
    exclude = ("smtp_password", "email_provider_config")
    readonly_fields = ("updated_at",)

from apps.integrations import admin_messaging  # noqa: F401
