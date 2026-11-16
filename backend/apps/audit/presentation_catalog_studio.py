"""Card Studio (decision 314/315): saved templates and applying one to a design. Ids and counts only."""

from django.utils.translation import gettext_noop
from .presentation_catalog_types import P

ENTRIES = (
    P("card_template.created", gettext_noop("Card template saved"), ("template_id", "kind", "stock", "design_id")),
    P("card_template.imported", gettext_noop("Card template imported"), ("template_id", "kind", "stock", "design_id")),
    P("card_template.updated", gettext_noop("Card template changed"), ("template_id", "fields")),
    P("card_template.deleted", gettext_noop("Card template deleted"), ("template_id",)),
    P("card_design.template_applied", gettext_noop("Template applied to a card design"),
      ("design_id", "template", "unplaced")),
    # CARD-STUDIO-2 (decisions 344/345): the artwork library and bulk cards from a CSV.
    P("card_design.asset_deleted", gettext_noop("Card artwork deleted from the library"), ("asset_id", "kind", "size_bytes")),
    P("card_design.csv_merged", gettext_noop("Cards printed from a CSV file"),
      ("design_id", "rows", "columns", "paper", "revision")),
)
