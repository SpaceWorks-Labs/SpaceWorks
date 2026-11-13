"""MODULE-UI: the /control/ capability matrix is laid out by area, without changing a posted value."""
import pytest

from apps.makerspaces.admin_capabilities import MakerspaceAdminForm
from apps.makerspaces.admin_capability_sections import capability_sections
from apps.makerspaces.module_registry import GROUPS
from tests.return_helpers import make_space

pytestmark = pytest.mark.django_db


def _options(form):
    return [{"value": value, "label": label, "selected": False} for value, label in form.fields["capabilities"].choices]


def test_every_choice_appears_exactly_once_in_group_order():
    form = MakerspaceAdminForm(instance=make_space("matrix-sections"))
    options = _options(form)
    sections = capability_sections(options)
    rendered = []
    for section in sections:
        for entry in section["modules"]:
            rendered += [entry["option"]["value"], *(o["value"] for o in entry["features"])]
        rendered += [o["value"] for o in section.get("loose_features", [])]
    assert sorted(rendered) == sorted(option["value"] for option in options)
    order = [group.key for group in GROUPS]
    keys = [s["key"] for s in sections if s["key"] in order]
    assert keys == sorted(keys, key=order.index)


def test_features_sit_under_their_parent_module():
    sections = capability_sections(_options(MakerspaceAdminForm(instance=make_space("matrix-parent"))))
    bookings = next(m for s in sections for m in s["modules"] if m["option"]["value"] == "module:bookings")
    assert "feature:bookings.recurring" in [o["value"] for o in bookings["features"]]
