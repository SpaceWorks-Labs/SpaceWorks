"""Card Studio: tenant-dump field snapshot and uniqueness for space card templates (see data_export `classification_studio`)."""
from apps.data_export.classification_studio import FIELDS as _FIELDS

FIELD_NAMES = {label: frozenset(names.split()) for label, names in _FIELDS.items()}
PROJECTED_LABELS = frozenset(FIELD_NAMES)


def unique_rules(remap, policy):
    """None: the template name is unique per space (`uniq_card_template_name` includes the makerspace), so it is no
    longer a deployment-global risk."""
    return {}
