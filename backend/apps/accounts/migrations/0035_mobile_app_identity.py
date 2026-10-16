"""Move public native identity configuration onto deployment registration rows."""

import base64
import binascii
import re

from django.conf import settings
from django.db import migrations, models


def backfill_identities(apps, schema_editor):
    Registration = apps.get_model("accounts", "NativeAppRegistration")
    Challenge = apps.get_model("accounts", "DeviceAttestationChallenge")
    alias = schema_editor.connection.alias
    declarations = getattr(settings, "DEVICE_ATTESTATION_APPS", {})
    for row in Registration.objects.using(alias).all().iterator():
        platform_entries = declarations.get(row.platform, {}) if isinstance(declarations, dict) else {}
        entry = platform_entries.get(row.verifier_config_key) if isinstance(platform_entries, dict) else None
        if (not isinstance(entry, dict) or not isinstance(entry.get("environments"), list)
                or row.environment not in entry["environments"]):
            continue
        value = entry.get("signing_identity")
        if not isinstance(value, str):
            continue
        if row.platform == "android":
            digest = value.replace(":", "")
            if re.fullmatch(r"[0-9a-fA-F]{64}", digest):
                value = digest.lower()
            else:
                try:
                    raw = base64.b64decode(value + "=" * (-len(value) % 4), altchars=b"-_", validate=True)
                except (ValueError, binascii.Error):
                    continue
                if len(raw) != 32:
                    continue
                value = raw.hex()
        elif row.platform != "apple" or not re.fullmatch(r"[A-Z0-9]{10}", value):
            continue
        Registration.objects.using(alias).filter(pk=row.pk).update(signing_identities=[value])
    # Old outstanding proofs retain exactly the scalar identity they were issued for.
    for challenge in Challenge.objects.using(alias).all().iterator():
        Challenge.objects.using(alias).filter(pk=challenge.pk).update(
            signing_identities=[challenge.signing_identity],
        )


class Migration(migrations.Migration):
    dependencies = [("accounts", "0034_phone_attestation_challenge")]
    operations = [
        migrations.AddField("nativeappregistration", "signing_identities", models.JSONField(default=list, blank=True)),
        migrations.AddField("nativeappregistration", "min_supported_version", models.CharField(max_length=64, null=True, blank=True)),
        migrations.AddField("deviceattestationchallenge", "signing_identities", models.JSONField(default=list, blank=True)),
        migrations.RunPython(backfill_identities, migrations.RunPython.noop),
    ]
