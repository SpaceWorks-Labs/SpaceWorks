"""Decision 340(b): the `printing` module is retired and folded into `machine_service`.

Machine service takes service requests for every machine type, so the 3D print queue is one machine
type inside it. These tests pin the fold end to end: the data migration (makerspaces/0154), the
alias that keeps a stored, restored or posted `printing` key working, and the registries that moved
with it (limits, reports, notifications, setup, profiles, editions, hosting plans).
"""

import pytest
from django.apps import apps
from django.db import connection

from apps.audit.models import AuditLog
from apps.makerspaces.migration_support.retire_printing_module import SOURCE, backwards, forwards
from apps.makerspaces.models import Makerspace
from apps.makerspaces.module_aliases import RETIRED_MODULE_ALIASES
from apps.makerspaces.module_registry import MODULE_KEYS, core_module_keys

pytestmark = pytest.mark.django_db


def _space(slug, modules):
    space = Makerspace.objects.create(name=slug, slug=slug)
    Makerspace.objects.filter(pk=space.pk).update(enabled_modules=sorted(set(modules)))
    space.refresh_from_db()
    return space


def _run(step):
    with connection.schema_editor() as editor:
        step(apps, editor)


def _modules(space):
    space.refresh_from_db()
    return set(space.enabled_modules)


# --- makerspaces/0154 ------------------------------------------------------------------------


def test_migration_folds_printing_into_machine_service_and_leaves_other_spaces_alone():
    core = core_module_keys()
    both = _space("fold-both", core | {"machines", "machine_service", "printing"})
    bare = _space("fold-bare", core | {"printing"})  # a direct write that skipped the dependency rule
    on = _space("fold-ms-only", core | {"machine_service"})
    off = _space("fold-off", core | {"events"})

    _run(forwards)

    assert _modules(both) == core | {"machines", "machine_service"}
    assert _modules(bare) == core | {"machine_service"}
    assert _modules(on) == core | {"machine_service"}
    assert _modules(off) == core | {"events"}  # never switched on for a space without printing
    rows = {row.makerspace_id: row.meta for row in AuditLog.objects.filter(
        action="makerspace.module_retired", meta__source=SOURCE)}
    assert set(rows) == {both.pk, bare.pk}
    assert rows[both.pk]["module"] == "printing" and rows[both.pk]["folded_into"] == "machine_service"
    assert rows[both.pk]["added_modules"] == [] and rows[bare.pk]["added_modules"] == ["machine_service"]

    _run(forwards)  # idempotent: nothing left to fold, no new rows
    assert AuditLog.objects.filter(action="makerspace.module_retired", meta__source=SOURCE).count() == 2


def test_migration_reverse_restores_each_folded_space_exactly():
    core = core_module_keys()
    both = _space("unfold-both", core | {"machine_service", "printing"})
    bare = _space("unfold-bare", core | {"printing"})
    off = _space("unfold-off", core | {"machine_service"})

    _run(forwards)
    _run(backwards)

    assert _modules(both) == core | {"machine_service", "printing"}
    assert _modules(bare) == core | {"printing"}  # machine_service was the migration's own addition
    assert _modules(off) == core | {"machine_service"}

    _run(backwards)  # idempotent
    assert _modules(both) == core | {"machine_service", "printing"}


def test_migration_is_chained_off_the_makerspaces_leaf():
    from importlib import import_module

    migration = import_module("apps.makerspaces.migrations.0154_retire_printing_module").Migration
    assert ("makerspaces", "0153_account_profile_merge") in migration.dependencies


# --- the alias ---------------------------------------------------------------------------------


def test_printing_is_not_a_module_and_aliases_machine_service():
    assert "printing" not in MODULE_KEYS
    assert RETIRED_MODULE_ALIASES["printing"] == "machine_service"


def test_a_stored_printing_key_reads_as_machine_service_everywhere():
    from apps.makerspaces.platform import available_modules, bootstrap_payload, module_enabled
    from apps.makerspaces.setup_areas import active_areas, area_status

    space = _space("alias-stored", core_module_keys() | {"machines", "printing"})

    assert module_enabled(space, "machine_service") is True
    assert module_enabled(space, "printing") is True
    assert "machine_service" in available_modules(space) and "printing" not in available_modules(space)
    payload = bootstrap_payload(space)
    assert "machine_service" in payload["modules"] and "printing" not in payload["modules"]
    assert "printing_requests" in payload["workflows"]
    assert area_status(space)["machines"] == "on" and active_areas(space)["machines"] is True


def test_asking_for_printing_follows_machine_service_and_names_it_when_off():
    from apps.makerspaces.guards import SurfaceOff, require_module
    from apps.makerspaces.platform import module_enabled

    space = _space("alias-off", core_module_keys() | {"machines"})

    assert module_enabled(space, "printing") is False
    with pytest.raises(SurfaceOff) as error:
        require_module(space, "printing")
    assert error.value.detail["module"] == "machine_service"


def test_creation_setup_and_hosting_plans_accept_the_retired_key():
    from apps.admin_api.serializers_creation_setup import MakerspaceCreationSetupSerializer
    from apps.managed_hosting.plans import validate_modules

    serializer = MakerspaceCreationSetupSerializer(data={"modules": ["printing", "events", "machine_service"]})
    assert serializer.is_valid(), serializer.errors
    assert serializer.validated_data["modules"] == ["machine_service", "events"]
    assert validate_modules(["printing", "events"]) == ["events", "machine_service"]


# --- what moved with it ------------------------------------------------------------------------


def test_limits_reports_and_switch_authority_belong_to_machine_service():
    from apps.makerspaces.limit_modules import KEY_MODULE
    from apps.makerspaces.module_switch_authority import LIMIT_GATED_MODULES
    from apps.operations.report_coverage import REPORT_MODULE_COVERAGE, check_report_module_coverage
    from apps.operations.report_coverage_contract import REPORT_COVERAGE_AREAS, REPORT_COVERAGE_CONTRACT
    from apps.operations.report_registry import report_definition

    assert KEY_MODULE["print"] == "machine_service"
    assert "print" in LIMIT_GATED_MODULES["machine_service"] and "printing" not in LIMIT_GATED_MODULES
    assert "printer-service" in REPORT_MODULE_COVERAGE["machine_service"].reports
    assert "printing" not in REPORT_MODULE_COVERAGE and "printing" not in REPORT_COVERAGE_CONTRACT
    assert "printing" not in REPORT_COVERAGE_AREAS
    assert report_definition("printer-service").required_modules == ("machine_service",)
    assert "printing" not in report_definition("module-operational-health").section_modules
    assert check_report_module_coverage() == []


def test_print_notifications_follow_machine_service():
    from apps.integrations.notification_enums import NotificationFeature
    from apps.integrations.recipients_selection import FEATURE_MODULES, feature_available

    assert FEATURE_MODULES[NotificationFeature.PRINTING] == "machine_service"
    on = _space("notify-on", core_module_keys() | {"machine_service"})
    off = _space("notify-off", core_module_keys())
    assert feature_available(on, "printing") is True
    assert feature_available(off, "printing") is False


def test_setup_profiles_editions_and_purge_plans_never_offer_printing():
    from apps.makerspaces.editions import EDITIONS, public_surface_available
    from apps.makerspaces.module_profiles import PROFILES, profile_modules
    from apps.makerspaces.module_purge_plans import NOT_SEPARABLE
    from apps.makerspaces.setup_areas import AREAS, modules_for

    assert AREAS["machines"] == ("machines", "machine_service")
    assert "printing" not in modules_for(list(AREAS))
    for profile in PROFILES:
        assert "printing" not in profile_modules(profile), profile
    for edition in EDITIONS.values():
        assert "printing" not in edition.hidden_module_keys
    assert "printing" not in NOT_SEPARABLE
    assert public_surface_available("printing") is public_surface_available("machine_service")


def test_events_edition_hides_the_print_queue_with_machine_service(settings):
    from apps.makerspaces.editions import public_surface_available

    settings.SPACEWORKS_EDITION = "events"
    assert public_surface_available("machine_service") is False
    assert public_surface_available("printing") is False
