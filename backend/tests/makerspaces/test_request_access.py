"""Who may submit a borrow request (owner decision #80): derived from the modules.

With member accounts: members (with `membership`) or any signed-in account. Without them:
the account-less contact path. No stored switch. These pin the derivation, its audit on
module changes, the `list_modules` report, and the anonymous refusal where accounts exist.
"""

import json
from io import StringIO

import pytest
from django.core.management import call_command, get_commands
from django.urls import reverse
from rest_framework.test import APIClient

from apps.audit.models import AuditLog
from apps.inventory.models import InventoryProduct
from apps.makerspaces.models import Makerspace
from apps.makerspaces.module_install import install_module
from apps.makerspaces.request_access import ACCOUNTS, CONTACT, MEMBERS, effective_policy
from tests.module_helpers import disable_module

pytestmark = pytest.mark.django_db

CORE_PLUS = ["public_inventory", "request_workflow", "staff_admin", "scanner",
             "evidence_uploads", "qr_management", "member_accounts"]


def _space(slug, *, modules):
    return Makerspace.objects.create(name=slug, slug=slug, enabled_modules=list(modules))


def test_the_switch_no_longer_exists_on_the_model():
    field_names = {field.name for field in Makerspace._meta.get_fields()}
    assert "anonymous_requests_enabled" not in field_names
    # The historic principal link stays so pre-removal requests remain readable.
    assert "anonymous_requester" in field_names


def test_policy_follows_member_accounts_then_membership():
    assert effective_policy(_space("ra-accounts", modules=CORE_PLUS)) == ACCOUNTS
    assert effective_policy(_space("ra-members", modules=[*CORE_PLUS, "membership"])) == MEMBERS
    no_accounts = [key for key in CORE_PLUS if key != "member_accounts"]
    assert effective_policy(_space("ra-contact", modules=no_accounts)) == CONTACT


def test_membership_requires_member_accounts_and_installing_it_pulls_them_in():
    from apps.makerspaces.module_registry import BY_KEY

    assert "member_accounts" in BY_KEY["membership"].requires_modules
    space = _space("ra-dependency", modules=[key for key in CORE_PLUS if key != "member_accounts"])

    added = install_module(space, "membership")

    space.refresh_from_db()
    assert {"membership", "member_accounts"} <= set(space.enabled_modules)
    assert "member_accounts" in added
    assert effective_policy(space) == MEMBERS


def test_a_new_makerspace_has_member_accounts_by_default():
    space = Makerspace.objects.create(name="ra-default", slug="ra-default")
    assert "member_accounts" in space.enabled_modules
    assert effective_policy(space) in (MEMBERS, ACCOUNTS)


def test_migration_0108_turns_member_accounts_on_for_membership_spaces_with_an_audit_entry():
    import importlib
    from types import SimpleNamespace

    from django.apps import apps as django_apps
    from django.db import connection

    broken = _space("ra-0108-broken", modules=[*[k for k in CORE_PLUS if k != "member_accounts"], "membership"])
    untouched = _space("ra-0108-untouched", modules=[k for k in CORE_PLUS if k != "member_accounts"])
    migration = importlib.import_module("apps.makerspaces.migrations.0108_membership_requires_member_accounts")

    migration.repair(django_apps, SimpleNamespace(connection=connection))

    broken.refresh_from_db()
    untouched.refresh_from_db()
    assert "member_accounts" in broken.enabled_modules
    assert "member_accounts" not in untouched.enabled_modules
    entry = AuditLog.objects.get(makerspace=broken, action="makerspace.capabilities_changed")
    assert entry.actor is None and entry.meta["added_modules"] == ["member_accounts"]
    assert not AuditLog.objects.filter(makerspace=untouched, action="makerspace.capabilities_changed").exists()


def test_installing_membership_records_the_accounts_to_members_move():
    space = _space("ra-accounts-to-members", modules=CORE_PLUS)

    install_module(space, "membership")

    entry = AuditLog.objects.filter(action="makerspace.capabilities_changed").latest("id")
    assert entry.meta["request_access"] == {"before": ACCOUNTS, "after": MEMBERS}


def test_an_unrelated_module_change_records_no_policy_meta():
    space = _space("ra-unrelated-audit", modules=CORE_PLUS)

    install_module(space, "telegram")

    entry = AuditLog.objects.filter(action="makerspace.capabilities_changed").latest("id")
    assert "request_access" not in entry.meta


def test_uninstalling_membership_returns_to_accounts():
    space = _space("ra-uninstall", modules=[*CORE_PLUS, "membership", "member_accounts"])

    disable_module(space, "membership")

    space.refresh_from_db()
    assert effective_policy(space) == ACCOUNTS


def test_set_request_access_command_is_gone():
    assert "set_request_access" not in get_commands()


def test_list_modules_json_reports_installed_keys_and_request_access():
    space = _space("ra-json", modules=CORE_PLUS)
    out = StringIO()

    call_command("list_modules", "--makerspace", space.slug, "--json", stdout=out)

    payload = json.loads(out.getvalue())
    assert payload["makerspace"] == space.slug
    assert payload["request_access"] == ACCOUNTS
    assert "request_workflow" in payload["installed"]


@pytest.mark.parametrize("membership", [False, True])
def test_an_anonymous_submission_is_refused_wherever_member_accounts_exist(membership):
    modules = [*CORE_PLUS, "membership"] if membership else CORE_PLUS
    space = _space(f"ra-view-{membership}", modules=modules)
    product = InventoryProduct.objects.create(
        makerspace=space, name="Multimeter", total_quantity=2, available_quantity=2, is_public=True,
    )

    response = APIClient().post(
        reverse("hardware_requests:request-submit", args=[space.slug]),
        {
            "contact_name": "Stranger",
            "contact_email": "stranger@example.test",
            "items": [{"product_id": product.id, "quantity": 1}],
        },
        format="json",
        HTTP_IDEMPOTENCY_KEY="ra-view-key",
    )

    assert response.status_code == 401
    assert not space.hardware_requests.exists()


def test_the_control_capability_matrix_audits_the_policy_change():
    """The `/control/` matrix saves the model directly, so it captures before/after itself."""
    from types import SimpleNamespace

    from django.contrib.admin import ModelAdmin
    from django.contrib.admin.sites import AdminSite

    from apps.accounts.models import User
    from apps.makerspaces.admin_capabilities import (
        MakerspaceAdminForm,
        MakerspaceCapabilityAdminMixin,
    )

    class _CapabilityAdmin(MakerspaceCapabilityAdminMixin, ModelAdmin):
        """The mixin relies on `super().save_model`, so it needs a real ModelAdmin."""

    space = _space("ra-control-matrix", modules=CORE_PLUS)
    form = MakerspaceAdminForm(instance=space)
    assert form.request_access_before == ACCOUNTS

    actor = User.objects.create_superuser(account_kind="platform", username="ra-control-actor", is_superuser=True)
    space.enabled_modules = [*CORE_PLUS, "membership", "member_accounts"]
    admin = _CapabilityAdmin(Makerspace, AdminSite())
    admin.save_model(SimpleNamespace(user=actor), space, form, change=True)

    entry = AuditLog.objects.filter(action="makerspace.capabilities_changed").latest("id")
    assert entry.meta["request_access"] == {"before": ACCOUNTS, "after": MEMBERS}
