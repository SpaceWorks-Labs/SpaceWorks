"""S-A guard checks: migrations, system checks, audit presentation and route classification."""

import pytest
from django.core.management import call_command

from apps.accounts.claim_routes import policy_for
from apps.accounts.claim_route_types import Refused
from apps.accounts.delegated_routes import MEMBER_ONLY, MEMBERSHIP_ONLY, SHARED_ACCOUNT_UTILITY, route_class
from apps.accounts.passkeys.urls import PASSKEY_ROUTE_NAMES


@pytest.mark.django_db
def test_models_match_the_migrations():
    from io import StringIO
    from apps.makerspaces.capabilities import default_enabled_features
    from apps.makerspaces.models import Makerspace, default_enabled_modules
    # The root conftest patches both field defaults; restore the production ones first.
    modules = Makerspace._meta.get_field("enabled_modules")
    features = Makerspace._meta.get_field("enabled_features")
    saved = modules.default, features.default
    modules.default, features.default = default_enabled_modules, default_enabled_features
    out = StringIO()
    try:
        call_command("makemigrations", "--check", "--dry-run", verbosity=1, stdout=out)
    except SystemExit:
        pytest.fail(out.getvalue())
    finally:
        modules.default, features.default = saved


@pytest.mark.django_db
def test_system_checks_pass():
    # The full `check` needs deployment keys (encryption.E001); the S-A checks run directly.
    from django.core.checks import run_checks
    problems = [item for item in run_checks(tags=["urls", "security", "database"])
                if item.id.startswith("accounts.")]
    assert problems == []
    from apps.accounts.passkeys.checks import passkey_rp_ids
    assert passkey_rp_ids() == []


def test_audit_presentation_catalogue_is_exact():
    from apps.audit.presentation_guards import presentation_catalog_errors
    assert presentation_catalog_errors() == []


def test_every_passkey_route_is_classified_and_refused_to_claim_sessions():
    from django.urls import reverse
    for name, kwargs in ((name, {"passkey_id": 1} if name == "auth-passkey-detail" else {})
                         for name in PASSKEY_ROUTE_NAMES):
        assert reverse(name, kwargs=kwargs).startswith("/api/v1/auth/")
    for name in PASSKEY_ROUTE_NAMES:
        assert route_class(name) in {MEMBER_ONLY, SHARED_ACCOUNT_UTILITY}, name
        for method in ("GET", "POST", "PATCH", "DELETE"):
            assert isinstance(policy_for(name, method), Refused)
    assert route_class("admin-staff-roles-mfa-reset") == MEMBERSHIP_ONLY


def test_authority_registry_still_declares_every_input():
    from apps.tenant_migration.authority_guards import validate_authority_registry
    validate_authority_registry()


def test_login_security_contract_names_s_a_codes():
    from apps.accounts import login_security_contract as contract
    for code in ("last_factor", "mfa_reset_not_allowed", "rp_id_unavailable", "passkey_failed",
                 "staff_session_expired", "passkeys_unavailable", "passkey_required", "mfa_required"):
        assert code in contract.ERROR_CODES
    for action in ("auth.mfa_reset", "auth.passkey_renamed"):
        assert action in contract.AUDIT_ACTIONS
