"""Decision 236 + addendum: own vs hosted spaces, and "default unlimited, the superadmin chooses"."""

import pytest
from rest_framework.exceptions import ValidationError

from apps.audit.models import AuditLog
from apps.makerspaces import limits
from apps.makerspaces.limits_core import suggested_limit
from apps.managed_hosting import billing, hosting_type, plans, trials
from apps.managed_hosting.limits_console import limit_rows
from apps.managed_hosting.models import HostingPlan, SpaceHostingType, SpacePlanAssignment
from apps.space_controls import health

from .helpers import api, space, superadmin

pytestmark = pytest.mark.django_db
PLATFORM = "/api/v1/admin/platform"


@pytest.fixture
def hosting(settings, own_by_default):
    """The console switch on, no platform domain; a row-less space is OWN (production default)."""
    settings.PLATFORM_DOMAIN_SUFFIX = ""
    settings.MANAGED_PLANS_ENABLED = True
    return settings


def _hosted(lab, root):
    return hosting_type.set_type(root, lab, hosting_type.HOSTED)


def test_a_new_space_is_own_and_ignores_plans_but_not_explicit_overrides(hosting):
    # Decision 281 addendum: an explicitly set limit applies to own spaces; plans stay hosted-only.
    lab, root = space(resource_limit_overrides={"custom_domain": False}), superadmin()
    plan = HostingPlan.objects.create(key="tiny", name="Tiny", limits={"members": 1})
    SpacePlanAssignment.objects.create(makerspace=lab, plan=plan)
    assert hosting_type.stored_type(lab) == "own" and not hosting_type.is_hosted(lab)
    for key in limits.NUMERIC_LIMIT_KEYS:
        assert limits.resource_limit(lab, key) is None
    limits.check_quota(lab, "members", adding=1000)
    assert limits.custom_domain_allowed(lab) is True
    rows = limit_rows(lab)
    assert rows["hosted"] is False and {row["source"] for row in rows["rows"]} == {"own"}
    lab.resource_limit_overrides = {"members": 1}
    lab.save(update_fields=["resource_limit_overrides"])
    assert limits.resource_limit(lab, "members") == 1
    assert root  # created after the space on purpose: nothing about the actor changes the answer


def test_default_is_unlimited_for_a_hosted_space_and_defaults_are_only_suggestions(hosting):
    lab, root = space(), superadmin()
    _hosted(lab, root)
    for key in limits.NUMERIC_LIMIT_KEYS:
        assert limits.resource_limit(lab, key) is None
    members = next(row for row in limit_rows(lab)["rows"] if row["key"] == "members")
    assert members["source"] == "unlimited" and members["suggested"] == suggested_limit("members")


def test_plan_applies_and_override_beats_plan_on_a_hosted_space(hosting):
    lab, root = space(), superadmin()
    _hosted(lab, root)
    plan = HostingPlan.objects.create(key="basic", name="Basic", limits={"members": 5})
    plans.assign(root, lab.pk, plan.pk, trial_days=0)
    assert limits.resource_limit(lab, "members") == 5
    lab.resource_limit_overrides = {"members": 9}
    lab.save(update_fields=["resource_limit_overrides"])
    assert limits.resource_limit(lab, "members") == 9
    lab.resource_limit_overrides = {"members": -1}
    lab.save(update_fields=["resource_limit_overrides"])
    assert limits.resource_limit(lab, "members") is None  # cleared to unlimited even with a plan


def test_switch_off_makes_every_space_own_and_keeps_the_stored_type(hosting):
    lab, root = space(), superadmin()
    _hosted(lab, root)
    plan = HostingPlan.objects.create(key="tiny-off", name="Tiny", limits={"members": 1})
    plans.assign(root, lab.pk, plan.pk, trial_days=0)
    assert limits.resource_limit(lab, "members") == 1
    hosting.MANAGED_PLANS_ENABLED = False
    assert not hosting_type.is_hosted(lab) and limits.resource_limit(lab, "members") is None
    assert SpaceHostingType.objects.get(makerspace=lab).hosting_type == "hosted"  # nothing deleted


def test_superadmin_changes_the_type_audited_and_others_cannot(hosting):
    lab, root = space(), superadmin()
    url = f"{PLATFORM}/spaces/{lab.pk}/hosting-type"
    assert api(root).get(url).json() == {"hosting_type": "own", "hosting_active": True, "hosted": False}
    response = api(root).put(url, {"hosting_type": "hosted"}, format="json")
    assert response.status_code == 200 and response.json()["hosted"] is True
    audit = AuditLog.objects.get(action="managed_hosting.hosting_type_changed", makerspace=lab)
    assert audit.meta["from"] is None and audit.meta["to"] == "hosted"
    assert api(root).put(url, {"hosting_type": "rented"}, format="json").status_code == 400
    from .helpers import manager
    assert api(manager(lab)).put(url, {"hosting_type": "own"}, format="json").status_code in (401, 403)


def test_plans_trials_and_invoices_need_a_hosted_space(hosting):
    from datetime import date

    lab, root = space(), superadmin()
    plan = HostingPlan.objects.create(key="trial", name="Trial", limits={}, trial_days=7)
    with pytest.raises(ValidationError):
        plans.assign(root, lab.pk, plan.pk)
    with pytest.raises(ValidationError):
        billing.create_invoice(root, {"makerspace_id": lab.pk, "description": "Hosting", "amount_minor": 100,
                                      "currency": "usd", "due_on": date(2026, 12, 1)})
    from django.utils import timezone
    SpacePlanAssignment.objects.create(makerspace=lab, plan=plan,
                                       trial_ends_at=timezone.now())  # a stale trial on an own space
    assert trials.sweep() == {"reminded": 0, "expired": 0}
    assert health.card(lab)["hosting_type"] == "own" and health.card(lab)["hosted"] is False


def test_a_space_from_a_hosting_request_is_hosted(hosting):
    from django.utils import timezone

    from apps.hosting_requests.models import HostingRequest
    from apps.hosting_requests import workflow

    root, lab = superadmin(), space()
    row = HostingRequest.objects.create(space_name="Guest Lab", applicant_email="a@example.test",
                                        status=HostingRequest.Status.ACCEPTED, source=HostingRequest.Source.PUBLIC,
                                        decided_at=timezone.now())
    workflow.link_created_makerspace(root, row.pk, lab)
    assert hosting_type.stored_type(lab) == "hosted"


def test_migration_marks_existing_spaces_own():
    from importlib import import_module

    from django.apps import apps as registry

    migration = import_module("apps.managed_hosting.migrations.0004_space_hosting_type")
    lab = space("pre-existing")
    SpaceHostingType.objects.filter(makerspace=lab).delete()
    migration.existing_spaces_are_own(registry, None)
    assert SpaceHostingType.objects.get(makerspace=lab).hosting_type == "own"
