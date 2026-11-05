"""Shop settings writes through L17's settings authority (#101, LANE-RULES §13).

Every changed field is checked with `assert_setting_write(actor, space, "shop", key)`
before anything is written (the Space Manager, or the Shop Manager by its fixed exception,
#137; an SM lock still binds the Shop Manager) and audited as `settings.changed`.
"""

from django.db import transaction
from rest_framework.exceptions import ValidationError

from apps.makerspaces.settings_authority import assert_setting_write, record_change

from .gates import write_allowed
from .models import ShopSettings

TEXT_FIELDS = ("policy_text", "pickup_note")


@transaction.atomic
def update_settings(space, row, values, *, actor):
    write_allowed(space)
    row = ShopSettings.objects.select_for_update().filter(makerspace=space).first() or row
    changed = {name: value for name, value in values.items() if getattr(row, name) != value}
    decisions = {name: assert_setting_write(actor, space, "shop", f"shop_{name}") for name in changed}
    before = {name: getattr(row, name) for name in changed}
    for name, value in changed.items():
        setattr(row, name, value)
    if row.second_reminder_days <= row.first_reminder_days:
        raise ValidationError({"second_reminder_days": "The second reminder comes after the first."})
    row.updated_by = actor
    row.save()
    for name in changed:
        # Buyer-facing text is not copied into the append-only audit row; numbers are.
        old, new = ("text", "changed text") if name in TEXT_FIELDS else (before[name], changed[name])
        record_change(actor, space, "shop", f"shop_{name}", old, new, decisions[name])
    return row
