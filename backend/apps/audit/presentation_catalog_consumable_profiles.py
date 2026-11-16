"""Decisions 341/343: per-type consumable profiles, machine-type templates and a job's consumables."""

from django.utils.translation import gettext_noop

from .presentation_catalog_types import P

ENTRIES = (
    P("machine_type_consumable.created", gettext_noop("Consumable added to a machine type")),  # metadata is denied by the wrapper-namespace policy
    P("machine_type_consumable.updated", gettext_noop("Machine type consumable changed")),  # metadata is denied by the wrapper-namespace policy
    P("machine_type_consumable.deleted", gettext_noop("Consumable removed from a machine type"), ("key",)),
    P("machine_type_consumable.deactivated", gettext_noop("Machine type consumable switched off"), ("key",)),
    P("machine_type_template.saved", gettext_noop("Machine type template saved"), ("key", "created")),
    P("machine_type_template.deleted", gettext_noop("Machine type template deleted"), ("key",)),
    P("machine_type.template_applied", gettext_noop("Machine type template applied"),
      ("template_key", "created_type", "consumables_added", "consumables_skipped")),
    P("machine_service.consumables_estimated", gettext_noop("Job consumables estimated")),  # metadata is denied by the wrapper-namespace policy
    P("machine_service.consumables_recorded", gettext_noop("Job consumables recorded")),  # metadata is denied by the wrapper-namespace policy
    P("machine_type_setup.updated", gettext_noop("Machine type setup changed"), ("fields",)),
    P("machine_type_setup.booking_defaults_applied", gettext_noop("Machine type booking defaults applied to its spaces"),
      ("spaces", "fields")),
    P("machine_type_document.added", gettext_noop("Machine type document added"), ("title", "size_bytes")),
    P("machine_type_document.removed", gettext_noop("Machine type document removed"), ("title",)),
    P("machine_service.consumable_stock_short", gettext_noop("Job consumable stock ran short")),  # metadata is denied by the wrapper-namespace policy
)
