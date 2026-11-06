"""Lane r2-parity-followups (#190): what the web console now does that only /control/ could."""

from .presentation_catalog_types import P

ENTRIES = (
    P("platform.provider_test", "Platform provider credentials tested", ("via", "provider", "outcome")),
    P("platform.sms_settings_updated", "Platform SMS settings changed", ("via", "created", "changed_fields")),
    P("platform.push_settings_updated", "Platform push settings changed", ("via", "created", "changed_fields")),
    P("platform.whatsapp_settings_updated", "Platform WhatsApp settings changed", ("via", "created", "changed_fields")),
    P("platform.attestation_settings_updated", "App attestation settings changed", ("via", "created", "changed_fields")),
    P("platform.login_methods_updated", "Sign-in methods changed", ("via", "created", "changed_fields")),
    P("backup.archive_key_job_queued", "Archive re-encryption or purge queued", ("via", "job")),
)
