"""Registered staff-shell projection used by the readable-main registry."""

from datetime import UTC, datetime

from django.apps import apps
from django.core.serializers.json import DjangoJSONEncoder
import json

from apps.makerspaces.staff_retirement import shell_values
from .raw_projection import concrete_record_payload

SHELL_TIMESTAMP = datetime(1970, 1, 1, tzinfo=UTC)

# Credential rows are sealed with their staff owner, never left with the public shell.
STAFF_CREDENTIAL_PATHS = {
    "accounts.UserMFA": "user__staff_makerspace",
    "accounts.MFAChallenge": "user__staff_makerspace",
    "accounts.ReauthenticationSession": "user__staff_makerspace",
    "accounts.EmailVerificationChallenge": "user__staff_makerspace",
    "accounts.PasswordResetEnvelope": "user__staff_makerspace",
    "accounts.PhoneVerificationChallenge": "user__staff_makerspace",
    "accounts.MemberClaimCode": "membership__user__staff_makerspace",
    "accounts.SocialIdentity": "user__staff_makerspace",
    "accounts.OidcBrowserAttempt": "intended_user__staff_makerspace",
    "accounts.DeviceGrant": "user__staff_makerspace",
    "accounts.DeviceRefreshFamily": "user__staff_makerspace",
    "accounts.DeviceRefreshToken": "family__user__staff_makerspace",
    "accounts.SocialLoginNonce": "device_grant__user__staff_makerspace",
    "token_blacklist.OutstandingToken": "user__staff_makerspace",
    "token_blacklist.BlacklistedToken": "token__user__staff_makerspace",
}


def shell_fixture(preimage):
    fields = dict(preimage["fields"])
    values = shell_values(preimage["pk"], SHELL_TIMESTAMP)
    values["staff_makerspace"] = values.pop("staff_makerspace_id")
    fields.update(values)
    return json.loads(json.dumps({**preimage, "fields": fields}, cls=DjangoJSONEncoder))


def staff_fixture(model, record):
    # Use the same lossless datetime conversion as raw reconstruction digests.
    normalized = concrete_record_payload(model, record)
    fields = {field.name: normalized[field.column] for field in model._meta.concrete_fields
              if not field.primary_key}
    return {"model": model._meta.label_lower,
            "pk": normalized[model._meta.pk.column], "fields": fields}


def project_staff_shells(cursor, marker):
    User = apps.get_model("accounts.User")
    quote = cursor.db.ops.quote_name
    cursor.execute(f'SELECT pk FROM {quote(marker)} ORDER BY pk')
    ids = [row[0] for row in cursor.fetchall()]
    for pk in ids:
        cursor.execute('SELECT staff_makerspace_id FROM accounts_user WHERE id = %s', [pk])
        owner = cursor.fetchone()[0]
        cursor.execute("SELECT set_config('app.account_retirement_makerspace_id', %s, true)", [str(owner)])
        values = shell_values(pk, SHELL_TIMESTAMP)
        cursor.execute("UPDATE accounts_user SET " + ", ".join(
            f"{quote(User._meta.get_field(name).column)} = %s" for name in values
        ) + " WHERE id = %s", [*values.values(), pk])
