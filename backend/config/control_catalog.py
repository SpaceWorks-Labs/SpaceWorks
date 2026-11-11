"""The /control/ catalogue (#188, regrouped for 0.12.0): every admin screen, its plain name, group and help.

This is the ONE place a /control/ screen is named. The sidebar (``config.unfold_sidebar``)
is built from it, the model-page help line (``templatetags/control_copy.py``) reads it, the
home dashboard's group map reads it, and ``tests/control_restructure_local/test_control_catalog.py``
plus ``tests/open_items_0120/test_control_admin_0120.py`` pin that every registered admin model
appears in exactly one group, or in the internal-records list. Adding an admin model means
adding its line here.

The groups follow the platform console's mental model (owner, 2026-11-11: "proper grouping"),
and the React platform console uses the same names in the same order.

Pure data: ``config.settings`` imports it (through ``config.unfold``) before any app loads,
so nothing here may import a model.
"""

from typing import NamedTuple

from django.utils.translation import gettext_lazy

from config.control_catalog_entries import HIDDEN_ENTRIES, SECTION_ENTRIES


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
    icon: str = ""
    description: str = ""


# Order is the sidebar's order. (key, title, Material Symbols icon, one-line description)
GROUPS = (
    ("overview", gettext_lazy("Overview"), "dashboard",
     gettext_lazy("Home, platform announcements and the background jobs that keep everything running.")),
    ("spaces", gettext_lazy("Spaces"), "store",
     gettext_lazy("Every space and organization: settings, lifecycle, requests and web addresses.")),
    ("people", gettext_lazy("People & roles"), "group",
     gettext_lazy("Accounts, who holds which role in which space, machine scope and member records.")),
    ("inventory", gettext_lazy("Inventory"), "inventory_2",
     gettext_lazy("Items, units, containers and QR codes, borrowing, stock changes and purchasing.")),
    ("machines", gettext_lazy("Machines"), "precision_manufacturing",
     gettext_lazy("Machines, jobs, materials, maintenance and connected devices.")),
    ("events", gettext_lazy("Events"), "event",
     gettext_lazy("Events and series, their organizers, registrations and ticket orders.")),
    ("bookings", gettext_lazy("Bookings"), "event_available",
     gettext_lazy("Rooms and areas people can book, and every booking.")),
    ("shop", gettext_lazy("Shop"), "storefront",
     gettext_lazy("What each space sells, its orders, returns and stock.")),
    ("money", gettext_lazy("Money"), "payments",
     gettext_lazy("The payments ledger, offline settlements, refunds, disputes, donations and payment settings.")),
    ("messaging", gettext_lazy("Messaging & notifications"), "notifications",
     gettext_lazy("Email, text, WhatsApp and push: providers, templates, delivery logs and who is told what.")),
    ("integrations", gettext_lazy("Integrations & analytics"), "hub",
     gettext_lazy("API clients, connected apps, analytics dashboards and the mobile apps.")),
    ("limits", gettext_lazy("Limits & hosting"), "speed",
     gettext_lazy("Per-space limits and quotas, hosting plans, request rates and storage use.")),
    ("recovery", gettext_lazy("Data & recovery"), "backup",
     gettext_lazy("Backups, off-site copies, restores, moving a space to another server and exports.")),
    ("security", gettext_lazy("Security & audit"), "shield",
     gettext_lazy("Sign-in methods and protection, personal-data windows, and the append-only audit trail.")),
)
SECTION_TITLES = tuple((key, title) for key, title, _icon, _description in GROUPS)


def _entry(row):
    key, title, icon, help_text = row
    if "." in key and ":" not in key:
        app_label, model_name = key.split(".")
        return Entry(key, title, icon, help_text, f"admin:{app_label}_{model_name}_changelist", True)
    return Entry(key, title, icon, help_text, key, False)


SECTIONS = tuple(
    Section(key, title, tuple(_entry(row) for row in SECTION_ENTRIES[key]), icon, description)
    for key, title, icon, description in GROUPS
)
# Registered read-only, reachable from "All records" and the home page, but kept out of the
# menu: bookkeeping rows nobody works in day to day.
HIDDEN = tuple(_entry(row) for row in HIDDEN_ENTRIES)
HIDDEN_MODELS = frozenset(entry.key for entry in HIDDEN)

MODEL_ENTRIES = {entry.key: entry for section in SECTIONS for entry in section.entries if entry.is_model}
MODEL_SECTIONS = {entry.key: section.key for section in SECTIONS for entry in section.entries if entry.is_model}
MODEL_ENTRIES.update({entry.key: entry for entry in HIDDEN})


def help_for(label_lower):
    """The one-line help shown above a model's list and form, or "" for an unknown model."""
    entry = MODEL_ENTRIES.get(label_lower)
    return entry.help if entry else ""


def title_for(label_lower):
    entry = MODEL_ENTRIES.get(label_lower)
    return entry.title if entry else ""
