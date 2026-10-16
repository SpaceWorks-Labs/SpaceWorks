from django.conf import settings
from django.core.checks import Error, Tags, Warning, register
from django.db import connections
from django.db.utils import OperationalError, ProgrammingError


@register(Tags.security)
def check_development_attestation(app_configs=None, **kwargs):
    if settings.DEVICE_ATTESTATION_DEV_INSECURE and not settings.DEBUG:
        return [Error(
            "Development-insecure device attestation requires DEBUG=True.",
            hint="Disable DEVICE_ATTESTATION_DEV_INSECURE before production use.",
            id="accounts.E001",
        )]
    return []


@register(Tags.database)
def check_legacy_native_identities(app_configs=None, databases=None, **kwargs):
    from apps.accounts.native_app_identity import eligible_registrations

    warnings = []
    for alias in databases or ["default"]:
        try:
            connection = connections[alias]
            table = "accounts_nativeappregistration"
            if table not in connection.introspection.table_names():
                continue
            with connection.cursor() as cursor:
                columns = {column.name for column in connection.introspection.get_table_description(cursor, table)}
            if "signing_identities" not in columns:
                continue  # The check also runs before migrate on existing installations.
            rows = list(eligible_registrations().using(alias).filter(signing_identities=[])
                        .values_list("pk", "app_id", "environment"))
        except (OperationalError, ProgrammingError):
            continue
        if rows:
            labels = ", ".join(f"#{pk} {app_id} ({environment})" for pk, app_id, environment in rows)
            warnings.append(Warning(
                f"Native registrations have no stored signing identities: {labels}",
                hint="Enter distribution signer digests or the App ID Prefix in /control/; legacy env fallback is temporary.",
                id="accounts.W001",
            ))
    return warnings
