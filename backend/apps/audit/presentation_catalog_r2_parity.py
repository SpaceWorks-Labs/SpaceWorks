"""Lane r2-parity-followups (#190): what the web console now does that only /control/ could."""

from django.utils.translation import gettext_lazy
from .presentation_catalog_types import P

ENTRIES = (
    P("platform.provider_test", gettext_lazy("Platform provider credentials tested"), ("via", "provider", "outcome")),
    P("platform.sms_settings_updated", gettext_lazy("Platform SMS settings changed"), ("via", "created", "changed_fields")),
    P("platform.push_settings_updated", gettext_lazy("Platform push settings changed"), ("via", "created", "changed_fields")),
    P("platform.whatsapp_settings_updated", gettext_lazy("Platform WhatsApp settings changed"), ("via", "created", "changed_fields")),
    P("platform.attestation_settings_updated", gettext_lazy("App attestation settings changed"), ("via", "created", "changed_fields")),
    P("platform.login_methods_updated", gettext_lazy("Sign-in methods changed"), ("via", "created", "changed_fields")),
    P("native_app.registration_updated", gettext_lazy("Mobile app identity saved"), ("via", "created", "changed_fields")),
    P("backup.archive_key_job_queued", gettext_lazy("Archive re-encryption or purge queued"), ("via", "job")),
)
