"""R4 audit B (#95, #183B): every module key and capability in the registry, switched off.

Iterates the LIVE registry, so a new key fails here until it is enforced in the backend,
known to the frontend, documented in docs/MODULES.md and given a purge plan. The
behavioural per-module probes live in tests/modules/test_module_contract_matrix.py; the
notification and scheduled-task maps in tests/modules/test_notification_source_map.py and
tests/modules/test_scheduled_task_sources.py; tombstoning in tests/separability.
"""

import pathlib
import re

import pytest
from rest_framework.test import APIClient

from apps.makerspaces.capabilities import FEATURES
from apps.makerspaces.guards import SurfaceOff
from apps.makerspaces.module_purge_plans import BY_KEY as PURGE_PLANS, NOT_SEPARABLE
from apps.makerspaces.module_registry import BY_KEY, MODULE_KEYS, core_module_keys

BACKEND = pathlib.Path(__file__).resolve().parents[2]
APPS = BACKEND / "apps"
FRONTEND = BACKEND.parent / "frontend" / "src"
DOCS = BACKEND.parent / "docs" / "MODULES.md"
OPTIONAL = sorted(MODULE_KEYS - set(core_module_keys()))
GUARD = r"(require_module[a-z_]*|module_enabled|module_off|module_available|require_module_for_servable)\("
# Keys enforced through a declared table instead of a literal guard call.
TABLE_ENFORCED = {"slack", "mattermost", "discord", "webhook", "sms", "whatsapp", "telegram", "guest_handover"}
# Capability families whose key is built from a domain at the call site.
COMPOSED_PREFIXES = ("charges.", "payments.", "membership.")


def _sources(root, suffixes):
    for path in root.rglob("*"):
        if path.suffix in suffixes and "migrations" not in path.parts and ".test." not in path.name \
                and "generated" not in path.parts and not path.name.startswith(("module_registry", "capability_definitions")):
            yield path, path.read_text(encoding="utf-8")


BACKEND_TEXT = dict(_sources(APPS, {".py"}))
FRONTEND_TEXT = dict(_sources(FRONTEND, {".ts", ".tsx"}))


def _quoted(key):
    return re.compile(r"[\"']" + re.escape(key) + r"[\"']")


@pytest.mark.parametrize("key", OPTIONAL)
def test_every_optional_module_is_gated_in_the_backend(key):
    guard = re.compile(GUARD + r"[^)]*[\"']" + re.escape(key) + r"[\"']")
    if any(guard.search(text) for text in BACKEND_TEXT.values()):
        return
    from apps.hardware_requests.view_helpers import HANDOVER_SURFACE_MODULE_KEYS
    from apps.integrations.notification_enums import CHANNEL_MODULE_KEYS

    assert key in TABLE_ENFORCED, f"{key}: no require_module/module_enabled call names it"
    assert key in set(CHANNEL_MODULE_KEYS.values()) | set(HANDOVER_SURFACE_MODULE_KEYS.values()), key


@pytest.mark.parametrize("key", OPTIONAL)
def test_every_optional_module_is_known_to_the_frontend(key):
    assert any(_quoted(key).search(text) for text in FRONTEND_TEXT.values()), (
        f"{key}: the frontend never gates on this module key")


@pytest.mark.parametrize("key", sorted(FEATURES))
def test_every_capability_is_enforced_in_the_backend(key):
    if key.startswith(COMPOSED_PREFIXES):
        return
    assert any(_quoted(key).search(text) for text in BACKEND_TEXT.values()), (
        f"{key}: no backend code reads this capability outside its definition")


@pytest.mark.parametrize("key", sorted(MODULE_KEYS))
def test_every_module_is_documented(key):
    text = DOCS.read_text(encoding="utf-8")
    assert re.search(rf"^### {re.escape(key)}\s*$", text, re.M), f"docs/MODULES.md has no ### {key} section"


def test_purge_plans_name_real_modules_and_say_what_they_delete():
    # A module absent from both owns no data of its own (`purge_module_data --list` says so).
    assert set(PURGE_PLANS) <= MODULE_KEYS and set(NOT_SEPARABLE) <= MODULE_KEYS
    assert not set(PURGE_PLANS) & set(NOT_SEPARABLE)
    for key, plan in PURGE_PLANS.items():
        assert plan.summary.strip() and callable(plan.delete), key
    # #183B(f): shared records have owners and require an explicit purge refusal.
    assert set(NOT_SEPARABLE) - set(core_module_keys()) == {
        "asset_units", "bulk_import", "containers", "email", "machines",
        "member_accounts", "mobile", "payments", "printing",
    }
    for key, reason in NOT_SEPARABLE.items():
        assert reason.strip(), key


def test_the_documented_key_count_matches_the_registry():
    text = DOCS.read_text(encoding="utf-8")
    match = re.search(r"The registry contains (\d+) keys", text)
    assert match and int(match.group(1)) == len(BY_KEY), (match and match.group(1), len(BY_KEY))
    for doc in (DOCS, BACKEND.parent / "README.md", BACKEND.parent / "docs" / "choosing-modules.md"):
        shipped = re.search(r"ships \*\*(\d+) modules\*\*", doc.read_text(encoding="utf-8"))
        assert shipped and int(shipped.group(1)) == len(BY_KEY), (doc.name, shipped and shipped.group(1))


# --- typed 404s fixed by this audit ---------------------------------------------------


@pytest.mark.django_db
def test_membership_capability_off_is_a_typed_404_naming_the_switch():
    from apps.makerspaces.membership_features import require_membership_feature
    from tests.return_helpers import make_space

    space = make_space("r4-membership-typed")
    with pytest.raises(SurfaceOff) as error:
        require_membership_feature(space, "import")
    assert error.value.detail["code"] in {"module_disabled", "feature_disabled"}
    space.enabled_modules = sorted({*space.enabled_modules, "membership", "member_accounts"})
    space.enabled_features = [key for key in space.enabled_features if key != "membership.import"]
    space.save(update_fields=["enabled_modules", "enabled_features"])
    with pytest.raises(SurfaceOff) as error:
        require_membership_feature(space, "import")
    assert error.value.detail == {"detail": "membership.import is turned off for this makerspace.",
                                  "code": "feature_disabled", "feature": "membership.import"}


@pytest.mark.django_db
def test_payment_rail_settings_need_the_payments_module_but_loan_rules_do_not(settings):
    from apps.makerspaces.models import MakerspaceMembership
    from apps.payments.models import MakerspacePaymentSettings
    from tests.accounts.reauth_helpers import force_recent_authenticate
    from tests.return_helpers import make_member, make_space

    # Reach the Connect module gate instead of the self-host-only 404.
    settings.PLATFORM_DOMAIN_SUFFIX = ".managed.test"
    space = make_space("r4-rail-off")
    space.enabled_modules = [key for key in space.enabled_modules if key != "payments"]
    space.save(update_fields=["enabled_modules"])
    manager = make_member("r4-rail-off-manager", space, membership_role=MakerspaceMembership.Role.SPACE_MANAGER)
    client = APIClient(HTTP_HOST="localhost")
    force_recent_authenticate(client, manager)
    url = f"/api/v1/admin/makerspace/{space.id}/payment-settings"
    refused = client.patch(url, {"stripe_secret_key": "sk_test_x"}, format="json")
    assert refused.status_code == 404 and refused.data["code"] == "module_disabled"
    assert refused.data["module"] == "payments"
    assert not MakerspacePaymentSettings.for_makerspace(space).get_stripe_secret_key()
    assert client.patch(url, {"loan_grace_days": 2, "default_currency": "inr"}, format="json").status_code == 200
    onboard = client.post(f"{url}/connect/onboard")
    assert onboard.status_code == 404 and onboard.data["code"] == "module_disabled"
    assert onboard.data["module"] == "payments"
    space.enabled_modules = sorted({*space.enabled_modules, "payments"})
    space.save(update_fields=["enabled_modules"])
    saved = client.patch(url, {"stripe_secret_key": "sk_test_x"}, format="json")
    assert saved.status_code == 200 and saved.data["stripe_secret_key_set"] is True
