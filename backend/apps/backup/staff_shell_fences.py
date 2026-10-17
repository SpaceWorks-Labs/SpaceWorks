"""Reserve low-entropy staff usernames without counting retained shells as deletes."""

from django.apps import apps

from .source_fences import digest

STAFF_USERNAME_FAMILY = {
    "version": "b1-staff-shell-username-fence-v1",
    "registry_identity": digest("staff-shell-source-username-v1"),
    "schema": "public", "table": "accounts_user", "columns": ["username"],
    "operations": ["insert", "update"],
}


def staff_username_fences(using, makerspace_components):
    User = apps.get_model("accounts.User")
    components = sorted(str(component) for maker, component in makerspace_components.items()
        if User._base_manager.using(using).filter(account_kind="staff", staff_makerspace_id=maker,
                                                 retired_at__isnull=True).exists())
    if not components:
        return ()
    definition = {**STAFF_USERNAME_FAMILY, "component_ids": components}
    return ({**definition, "definition_sha256": digest(definition)},)


def validate_supplemental_fence(fact):
    """No unregistered table, column, operation or unsigned exception is accepted."""
    if set(fact) != {*STAFF_USERNAME_FAMILY, "component_ids", "definition_sha256"}:
        raise ValueError("Unknown supplemental reservation fence.")
    if any(fact[name] != value for name, value in STAFF_USERNAME_FAMILY.items()):
        raise ValueError("Supplemental reservation fence drifted.")
    definition = {key: value for key, value in fact.items() if key != "definition_sha256"}
    if fact["definition_sha256"] != digest(definition):
        raise ValueError("Supplemental reservation fence digest differs.")
