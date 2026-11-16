"""MP-28: the /control/ module matrix completes an incomplete tick-list, with a notice."""

import pytest
from django.contrib.auth import get_user_model
from django.test import RequestFactory

from apps.audit.models import AuditLog
from apps.makerspaces.admin_capabilities import MakerspaceAdminForm, MakerspaceCapabilityAdminMixin
from apps.makerspaces.models import Makerspace
from apps.makerspaces.module_registry import core_module_keys


def _fresh(name, slug):
    # Only core is on before, so nothing in these tick tests counts as an untick.
    return Makerspace(name=name, slug=slug, enabled_modules=sorted(core_module_keys()), enabled_features=[])


def _clean(instance, values):
    form = MakerspaceAdminForm(instance=instance)
    form.cleaned_data = {"capabilities": values}
    form.clean_capabilities()
    return form


def test_ticking_a_module_without_its_requirements_adds_them():
    instance = _fresh(name="Matrix", slug="matrix")
    form = _clean(instance, ["module:event_reimbursements"])
    assert {"event_reimbursements", "events"} <= set(instance.enabled_modules)
    assert form.capability_dependencies_added == ["events"]


def test_a_retired_module_key_ticks_the_module_it_was_folded_into():
    # Decision 340b: an old form post naming `printing` means Machine service.
    instance = _fresh(name="Retired", slug="retired-printing")
    form = _clean(instance, ["module:printing"])
    assert "machine_service" in instance.enabled_modules
    assert "printing" not in instance.enabled_modules
    assert form.capability_dependencies_added == []
    assert "module:printing" not in [value for value, _label in MakerspaceAdminForm(instance=instance).fields["capabilities"].choices]


def test_a_feature_ticked_without_its_parent_adds_the_parent_transitively():
    instance = _fresh(name="Feature", slug="feature-parent")
    form = _clean(instance, ["feature:maintenance.reminders", "module:notifications"])
    assert "machines" in set(instance.enabled_modules)
    # #87 / LANE-RULES §9: the required feature is ticked too, with its parent.
    assert form.capability_dependencies_added == ["machines", "machines.maintenance"]
    assert {"maintenance.reminders", "machines.maintenance"} <= set(instance.enabled_features)


def test_a_complete_selection_reports_no_additions():
    instance = _fresh(name="Complete", slug="complete")
    form = _clean(instance, ["module:events", "module:event_reimbursements"])
    assert form.capability_dependencies_added == []
    assert set(instance.enabled_modules) == core_module_keys() | {"events", "event_reimbursements"}


def test_a_dependency_this_deployment_does_not_ship_is_refused(monkeypatch):
    monkeypatch.setattr(
        "apps.makerspaces.admin_capabilities.module_available", lambda key: key != "events"
    )
    with pytest.raises(Exception, match="events"):
        _clean(_fresh(name="Tomb", slug="tomb"), ["module:event_reimbursements"])


class _Base:
    def save_model(self, request, obj, form, change):
        obj.save()


class _Admin(MakerspaceCapabilityAdminMixin, _Base):
    def __init__(self):
        self.notices = []

    def message_user(self, request, message, level):
        self.notices.append(message)


@pytest.mark.django_db
def test_save_shows_a_notice_and_audits_the_added_dependencies():
    user = get_user_model().objects.create_superuser("root-mp28", "root-mp28@example.com", "pw-unused-1")
    space = Makerspace.objects.create(name="Saved", slug="saved-mp28")
    space.enabled_modules = sorted(core_module_keys())
    space.save(update_fields=["enabled_modules"])
    form = _clean(space, ["module:event_reimbursements"])
    request = RequestFactory().post("/control/")
    request.user = user
    admin = _Admin()
    admin.save_model(request, space, form, change=True)

    assert len(admin.notices) == 1 and "Events" in admin.notices[0]
    entry = AuditLog.objects.get(action="makerspace.capabilities_changed", makerspace=space)
    assert entry.meta["dependencies_added"] == ["events"]


# Owner decision #87: unticking cascades down, with a notice; nothing is re-ticked on save.

def _clean_from(enabled_modules, enabled_features, values):
    instance = Makerspace(name="Untick", slug="untick", enabled_modules=enabled_modules,
                          enabled_features=enabled_features)
    form = MakerspaceAdminForm(instance=instance)
    form.cleaned_data = {"capabilities": values}
    form.clean_capabilities()
    return instance, form


@__import__("pytest").mark.skip(reason="Decision 319: certification gating retired (machine access grants replace it); see tests/parity_0120/machine_access.")
def test_unticking_a_module_unticks_its_features_instead_of_reticking_it():
    before = sorted(core_module_keys() | {"machines"})
    instance, form = _clean_from(before, ["machines.certifications"], ["feature:machines.certifications"])
    assert "machines" not in instance.enabled_modules
    assert "machines.certifications" not in instance.enabled_features
    assert form.capability_turned_off == ["machines.certifications"]
    assert form.capability_dependencies_added == []


def test_unticking_a_module_unticks_dependent_modules_and_their_features():
    before = sorted(core_module_keys() | {"events", "event_reimbursements", "notifications", "machines"})
    values = ["module:event_reimbursements", "module:notifications", "module:machines", "feature:events.hackathons"]
    instance, form = _clean_from(before, ["events.hackathons"], values)
    assert not {"events", "event_reimbursements"} & set(instance.enabled_modules)
    assert "notifications" in instance.enabled_modules
    assert instance.enabled_features == []
    assert form.capability_turned_off == ["event_reimbursements", "events.hackathons"]


def test_unticking_a_core_module_turns_nothing_off():
    core = sorted(core_module_keys())
    instance, form = _clean_from(core, [], [f"module:{key}" for key in core[1:]])
    assert set(instance.enabled_modules) == set(core)
    assert form.capability_turned_off == []


@__import__("pytest").mark.skip(reason="Decision 319: certification gating retired (machine access grants replace it); see tests/parity_0120/machine_access.")
@pytest.mark.django_db
def test_save_notices_and_audits_what_an_untick_turned_off():
    user = get_user_model().objects.create_superuser("root-mp87", "root-mp87@example.com", "pw-unused-1")
    space = Makerspace.objects.create(name="Saved off", slug="saved-mp87")
    space.enabled_modules = sorted(set(space.enabled_modules) | {"machines"})
    space.enabled_features = ["machines.certifications"]
    space.save(update_fields=["enabled_modules", "enabled_features"])
    form = MakerspaceAdminForm(instance=space)
    form.cleaned_data = {"capabilities": ["feature:machines.certifications"]}
    form.clean_capabilities()
    request = RequestFactory().post("/control/")
    request.user = user
    admin = _Admin()
    admin.save_model(request, space, form, change=True)

    assert any("turned off" in notice for notice in admin.notices)
    entry = AuditLog.objects.get(action="makerspace.capabilities_changed", makerspace=space)
    assert entry.meta["dependents_turned_off"] == ["machines.certifications"]


def test_the_page_script_receives_the_servers_rules():
    from apps.makerspaces.admin_capability_completion import matrix_rules

    rules = matrix_rules()
    assert rules["features"]["feature:maintenance.reminders"]["parent"] == "module:machines"
    assert "module:machines" in rules["features"]["feature:maintenance.reminders"]["needs"]
    assert rules["features"]["feature:maintenance.reminders"]["requires_features"] == ["feature:machines.maintenance"]
    assert rules["modules"]["module:event_reimbursements"]["requires"] == ["module:events"]
    assert "module:printing" not in rules["modules"]  # retired into machine_service (340b)
    html = MakerspaceAdminForm(instance=Makerspace(name="Html", slug="html"))["capabilities"].as_widget()
    import re
    assert 'id="capability-rules"' in html and not re.search(r"<input[^>]*disabled", html)
