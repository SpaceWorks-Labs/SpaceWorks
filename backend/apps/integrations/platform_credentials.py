"""Platform provider credentials (SMS, push, WhatsApp, app attestation) from the web console (#190).

These four singletons were host-only: /control/ was the only place to enter them. The web
console now edits them through the SAME Django forms /control/ uses, so validation,
encryption at rest (``apps.makerspaces.secrets``) and the sender-reservation sync are one
code path, not two that can drift.

Secrets are write-only. The payload says only whether each one is set, and when and by
whom it last changed (read from the audit rows, which name changed FIELDS, never values).
"""

from dataclasses import dataclass, field

from django.forms.models import model_to_dict

from apps.audit import services as audit
from apps.audit.models import AuditLog


@dataclass(frozen=True)
class Spec:
    key: str
    audit_action: str
    public: tuple                                  # readable, writable plain fields
    secrets: dict = field(default_factory=dict)    # API name -> (form raw field, form clear field)
    test: str = ""                                 # "send" | "check" | ""

    @property
    def model(self):
        return self.form._meta.model

    @property
    def form(self):
        return _FORMS[self.key]()


def _sms_form():
    from apps.integrations.admin_sms import PlatformSmsSettingsForm
    return PlatformSmsSettingsForm


def _push_form():
    from apps.integrations.admin_push import PlatformPushSettingsForm
    return PlatformPushSettingsForm


def _whatsapp_form():
    from apps.integrations.admin_messaging import PlatformWhatsAppSettingsForm
    return PlatformWhatsAppSettingsForm


def _attestation_form():
    from apps.accounts.admin_attestation import PlatformAttestationSettingsForm
    return PlatformAttestationSettingsForm


def _login_methods_form():
    from apps.accounts.admin_social import PlatformLoginMethodsForm
    return PlatformLoginMethodsForm


_FORMS = {"sms": _sms_form, "push": _push_form, "whatsapp": _whatsapp_form, "attestation": _attestation_form,
          "login_methods": _login_methods_form}

SPECS = {spec.key: spec for spec in (
    Spec("sms", "platform.sms_settings_updated",
         ("is_enabled", "provider", "account_sid", "from_number", "notifications_enabled", "notifications_from_number"),
         {"auth_token": ("auth_token_raw", "clear_auth_token")}, test="send"),
    Spec("push", "platform.push_settings_updated", ("apns_team_id", "apns_key_id", "apns_topic"),
         {"fcm_service_account": ("fcm_service_account_raw", "clear_fcm_credentials"),
          "apns_private_key": ("apns_private_key_raw", "clear_apns_credentials")}, test="check"),
    Spec("whatsapp", "platform.whatsapp_settings_updated", ("is_enabled", "app_id", "phone_number_id", "business_account_id"),
         {"access_token": ("access_token_raw", "clear_access_token"),
          "app_secret": ("app_secret_raw", "clear_app_secret")}, test="check"),
    Spec("attestation", "platform.attestation_settings_updated", ("app_display_name",),
         {"play_integrity_service_account": ("play_integrity_service_account_raw", "clear_play_integrity_credentials")}),
    # No secret: which ways in the deployment offers (validate_login_methods refuses a lock-out).
    Spec("login_methods", "platform.login_methods_updated",
         ("password_enabled", "social_enabled", "phone_enabled", "self_registration_enabled", "passkeys_enabled")),
)}


def record_save(actor, key, row, created, changed_fields):
    """The same audit action /control/ writes, one literal call per provider, field names only."""
    if key == "sms":
        audit.record(actor, "platform.sms_settings_updated", target=row,
                     meta={"via": "console", "created": created, "changed_fields": changed_fields})
    elif key == "push":
        audit.record(actor, "platform.push_settings_updated", target=row,
                     meta={"via": "console", "created": created, "changed_fields": changed_fields})
    elif key == "whatsapp":
        audit.record(actor, "platform.whatsapp_settings_updated", target=row,
                     meta={"via": "console", "created": created, "changed_fields": changed_fields})
    elif key == "attestation":
        audit.record(actor, "platform.attestation_settings_updated", target=row,
                     meta={"via": "console", "created": created, "changed_fields": changed_fields})
    else:
        audit.record(actor, "platform.login_methods_updated", target=row,
                     meta={"via": "console", "created": created, "changed_fields": changed_fields})


def current_row(spec):
    """The singleton, or an unsaved default -- a read never creates the row."""
    return spec.model.objects.filter(pk=1).first() or spec.model()


def form_data(spec, row, body):
    """The full form input: today's values, overlaid with the API body in form field names."""
    # Every model field, not only the writable ones: a form field missing from the data
    # would read as empty/False (login methods' read-only MFA switch, for one).
    data = model_to_dict(row)
    for name in spec.public:
        if name in body:
            data[name] = body[name]
    for name, (raw, clear) in spec.secrets.items():
        data[raw] = body.get(name) or ""
        data[clear] = bool(body.get("clear_" + name))
    return data


def _changes(spec):
    return AuditLog.objects.filter(action=spec.audit_action, makerspace__isnull=True).select_related("actor").order_by("-pk")


def _stamp(row):
    if row is None:
        return {"at": None, "by": None}
    return {"at": row.created_at, "by": getattr(row.actor, "username", None)}


def payload(spec, row):
    changes = list(_changes(spec)[:50])
    secrets = []
    for name, (raw, clear) in spec.secrets.items():
        touched = next((change for change in changes
                        if {raw, clear} & set((change.meta or {}).get("changed_fields") or ())), None)
        secrets.append({"name": name, "set": bool(getattr(row, name, "")), "last_changed": _stamp(touched)})
    extra = {}
    if spec.key == "whatsapp":
        from apps.integrations.messaging.resolver import webhook_urls
        # Meta asks for both when the webhook is set up; the verify token is generated
        # here, never entered, and /control/ shows it read-only too.
        extra = {"webhook_verify_token": row.webhook_verify_token if row.pk else "",
                 "callback_url": webhook_urls("whatsapp")["callback"]}
    return {
        "provider": spec.key,
        "values": {name: getattr(row, name) for name in spec.public},
        "secrets": secrets,
        "info": extra,
        "updated_at": row.updated_at if row.pk else None,
        "last_changed": _stamp(changes[0] if changes else None),
        "test": spec.test or None,
    }
