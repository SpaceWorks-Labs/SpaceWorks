"""The /control/ catalogue (#188): every admin screen, its plain name, section and one-line help.

This is the ONE place a /control/ screen is named. The sidebar (``config.unfold_sidebar``)
is built from it, the model-page help line (``templatetags/control_copy.py``) reads it, and
``tests/control_restructure_local/test_control_catalog.py`` pins that every registered admin
model appears in exactly one section. Adding an admin model means adding its line here.

Pure data: ``config.settings`` imports it (through ``config.unfold``) before any app loads,
so nothing here may import a model.
"""

from django.utils.translation import gettext_lazy

from typing import NamedTuple

from config.control_catalog_entries import SECTION_ENTRIES


class Entry(NamedTuple):
    key: str          # "app_label.model_name" for a model, or the URL name of a page
    title: str
    icon: str
    help: str
    route: str
    is_model: bool


class Section(NamedTuple):
    key: str
    title: str
    entries: tuple


# Order is the sidebar's order (#188).
SECTION_TITLES = (
    ("overview", gettext_lazy("Overview")),
    ("makerspaces", gettext_lazy("Makerspaces")),
    ("organizations", gettext_lazy("Organizations")),
    ("people", gettext_lazy("People & access")),
    ("security", gettext_lazy("Security")),
    ("money", gettext_lazy("Money")),
    ("events", gettext_lazy("Events & programmes")),
    ("machines", gettext_lazy("Machines & devices")),
    ("inventory", gettext_lazy("Inventory & lending")),
    ("backups", gettext_lazy("Backups & recovery")),
    ("integrations", gettext_lazy("Integrations & messaging")),
    ("audit", gettext_lazy("Audit & logs")),
    ("system", gettext_lazy("System")),
)


def _entry(row):
    key, title, icon, help_text = row
    if "." in key and ":" not in key:
        app_label, model_name = key.split(".")
        return Entry(key, title, icon, help_text, f"admin:{app_label}_{model_name}_changelist", True)
    return Entry(key, title, icon, help_text, key, False)


SECTIONS = tuple(
    Section(key, title, tuple(_entry(row) for row in SECTION_ENTRIES[key]))
    for key, title in SECTION_TITLES
)

MODEL_ENTRIES = {entry.key: entry for section in SECTIONS for entry in section.entries if entry.is_model}
MODEL_SECTIONS = {entry.key: section.key for section in SECTIONS for entry in section.entries if entry.is_model}


def help_for(label_lower):
    """The one-line help shown above a model's list and form, or "" for an unknown model."""
    entry = MODEL_ENTRIES.get(label_lower)
    return entry.help if entry else ""


def title_for(label_lower):
    entry = MODEL_ENTRIES.get(label_lower)
    return entry.title if entry else ""
