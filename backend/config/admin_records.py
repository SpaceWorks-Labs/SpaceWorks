"""Read-only /control/ record lists for models the web console owns (0.12.0).

The payments ledger, shop, events, roles, analytics connections and the rest are worked in the
web console through their services, which lock, check and audit every write. /control/ shows
them for reference only: no add, change or delete, and so no parity row is needed (#190).

What a record page shows is decided here, once, for all of them:

* a field that could hold a secret shows only "Set" / "Not set";
* a field registered as scoped personal data, or a person's name or contact field, is left out
  (open the person's account behind an audited window instead);
* an account or a membership is shown by id, linked to its masked page;
* JSON is shown indented; binary and search-index columns are left out.
"""

from django.db import models
from unfold.admin import ModelAdmin

from config.admin_access import SuperuserOnlyModelAdmin
from config.admin_display import account_link, is_secret_name, membership_link, pretty_json, secret_state

PERSONAL_NAMES = frozenset({
    "name", "email", "phone", "first_name", "last_name", "display_name", "guest_name", "guest_email", "donor_name",
    "donor_email", "donor_note", "destination", "provider_subject", "custom_answers", "member_reason", "address",
})
SKIPPED_TYPES = ("BinaryField", "SearchVectorField")
SECRET, ACCOUNT, MEMBERSHIP, JSON = "secret__", "account__", "membership__", "json__"


def _registry_pii(model):
    try:
        from apps.accounts.pii_presentation import registry_field_names

        return frozenset(registry_field_names(model._meta.label))
    except Exception:  # noqa: BLE001 - an unknown label simply has no registered fields
        return frozenset()


def record_fields(model, hidden=()):
    """The ordered, safe-to-show field names (or generated display names) for a record page."""
    from apps.accounts.models import User

    personal = PERSONAL_NAMES | _registry_pii(model) | frozenset(hidden)
    names = []
    for field in model._meta.concrete_fields:
        if field.name in personal or field.get_internal_type() in SKIPPED_TYPES:
            continue
        remote = getattr(field.remote_field, "model", None)
        if remote is User:
            names.append(f"{ACCOUNT}{field.name}")
        elif remote is not None and remote._meta.label == "makerspaces.MakerspaceMembership":
            # A membership's own text names its person; show it by id like an account.
            names.append(f"{MEMBERSHIP}{field.name}")
        elif is_secret_name(field.name):
            names.append(f"{SECRET}{field.name}")
        elif isinstance(field, models.JSONField):
            names.append(f"{JSON}{field.name}")
        else:
            names.append(field.name)
    return tuple(names)


class ControlRecordAdmin(SuperuserOnlyModelAdmin, ModelAdmin):
    # The ORM lookup that names the row's space, or None for a platform-wide model.
    makerspace_lookup = "makerspace_id"
    hidden_fields = ()
    list_per_page = 50

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False

    def resolve_hidden_lookup(self):
        return self.makerspace_lookup

    def get_fields(self, request, obj=None):
        return record_fields(self.model, self.hidden_fields)

    def get_readonly_fields(self, request, obj=None):
        return self.get_fields(request, obj)

    def __getattr__(self, name):
        # Generated display callables, resolved by name like any admin method.
        for prefix, render in ((SECRET, secret_state), (ACCOUNT, account_link), (MEMBERSHIP, membership_link)):
            if name.startswith(prefix):
                return self._display(name.removeprefix(prefix), lambda obj, field: render(obj, field))
        if name.startswith(JSON):
            return self._display(name.removeprefix(JSON), lambda obj, field: pretty_json(getattr(obj, field)))
        raise AttributeError(name)

    def _display(self, field_name, render):
        from django.contrib import admin

        try:
            label = self.model._meta.get_field(field_name).verbose_name
        except Exception:  # noqa: BLE001
            label = field_name.replace("_", " ")
        return admin.display(description=label)(lambda obj: render(obj, field_name))
