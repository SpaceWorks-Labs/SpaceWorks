"""The lock floor holds on every writer of enabled_features (owner #111 Q9).

Generic writers cannot change a security key at all (the stored value is kept); the
security service can, but never below a platform lock's floor.
"""

import ast
from pathlib import Path

import pytest
from django.conf import settings

from apps.accounts.mfa_policy import required
from apps.makerspaces import security_settings as service
from apps.makerspaces.models import Makerspace
from tests.accounts.account_factories import make_staff

pytestmark = pytest.mark.django_db


# Release 2 (S-A) retired the only feature-backed security key, security.staff_mfa_required:
# staff MFA is a platform rule. The enabled_features guard stays for any future feature-backed
# row; the policy-backed rows are covered by test_security_policy_storage.py.


def test_staff_mfa_ignores_the_retired_key():
    space = Makerspace.objects.create(name="Locks", slug="locks-space")
    staff = make_staff(space, username="locks-inventory", role_slug="inventory_manager")
    assert required(staff) is True
    assert "security.staff_mfa_required" not in service.registry.BY_KEY


def _queryset_updates_of_enabled_features(path):
    tree = ast.parse(path.read_text(encoding="utf-8"))
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call) or not isinstance(node.func, ast.Attribute):
            continue
        if node.func.attr == "update" and any(keyword.arg == "enabled_features" for keyword in node.keywords):
            yield node.lineno
        if node.func.attr == "bulk_update" and any(
                isinstance(arg, (ast.List, ast.Tuple)) and any(
                    isinstance(item, ast.Constant) and item.value == "enabled_features" for item in arg.elts)
                for arg in [*node.args, *(keyword.value for keyword in node.keywords)]):
            yield node.lineno


def test_no_queryset_update_bypasses_the_security_guard():
    """`.update(enabled_features=...)` skips pre_save, so the lock floor and audit would too."""
    root = Path(settings.BASE_DIR) / "apps"
    offenders = [f"{path.relative_to(root)}:{line}" for path in root.rglob("*.py")
                 if "migrations" not in path.parts for line in _queryset_updates_of_enabled_features(path)]
    assert offenders == []
