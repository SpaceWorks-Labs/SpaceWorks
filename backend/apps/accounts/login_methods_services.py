"""Transactional operator writes shared by setup and the recovery command."""

from django.utils.translation import gettext
from django.core.exceptions import ValidationError
from django.db import transaction

from apps.accounts.audit_events import record_auth_event
from apps.accounts.login_methods_validation import validate_login_methods
from apps.accounts.models_login_methods import PlatformLoginMethods

BUILTIN_PROVIDERS = ("google", "apple", "github")


def parse_providers(value):
    if value in ("", "none"):
        return set()
    providers = [part.strip() for part in value.split(",")]
    if any(part not in BUILTIN_PROVIDERS for part in providers):
        raise ValidationError(gettext("Use google,apple,github as a comma list, or none."))
    return set(providers)


def setup_login_methods_from_environment(actor):
    import os

    if PlatformLoginMethods.objects.filter(pk=1).exists():
        return PlatformLoginMethods.objects.get(pk=1)
    # Missing setup env preserves the all-on defaults for manual/bootstrap callers.
    mfa = os.getenv("SETUP_MFA_ENABLED")
    providers = os.getenv("SETUP_SOCIAL_PROVIDERS")
    changes = {}
    if mfa is not None:
        if mfa.lower() not in ("y", "n", "yes", "no"):
            raise ValidationError(gettext("SETUP_MFA_ENABLED must be y or n."))
        changes["mfa_enabled"] = mfa.lower() in ("y", "yes")
    if providers is not None:
        selected = parse_providers(providers)
        changes.update({f"{provider}_enabled": provider in selected for provider in BUILTIN_PROVIDERS})
    return update_login_methods(changes, actor=actor, only_create=True)


@transaction.atomic
def update_login_methods(changes, *, actor=None, only_create=False):
    # get_or_create's PK conflict handling serializes concurrent first-time setup;
    # the explicit row lock serializes subsequent command updates.
    row, created = PlatformLoginMethods.objects.get_or_create(pk=1)
    row = PlatformLoginMethods.objects.select_for_update().get(pk=row.pk)
    if only_create and not created:
        return row
    current = PlatformLoginMethods(**{f.name: getattr(row, f.name) for f in row._meta.fields})
    for field, value in changes.items():
        setattr(row, field, value)
    validate_login_methods(row, current=current)
    row.save()
    record_auth_event(
        actor, "platform.login_methods_updated", target=row,
        meta={"fields": sorted(changes), "source": "setup" if only_create else "command"},
    )
    return row
