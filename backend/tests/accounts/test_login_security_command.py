"""S-C: host recovery, ``manage.py login_security --allow | --unblock | --list``."""

from datetime import timedelta
from io import StringIO

import pytest
from django.core.management import CommandError, call_command
from django.test import RequestFactory
from django.utils import timezone

from apps.accounts import ip_guard
from apps.accounts.models import IPAccessRule, IPAutoBlock, User
from apps.audit.models import AuditLog

pytestmark = pytest.mark.django_db


def run(*args):
    out = StringIO()
    call_command("login_security", *args, stdout=out)
    return out.getvalue()


@pytest.fixture
def root():
    return User.objects.create_user(username="root-cmd", password="Root password 77!", account_kind="platform",
                                    role=User.Role.SUPERADMIN, is_superuser=True, is_staff=True)


def _block(address):
    return ip_guard.block(ip_guard.client_source(RequestFactory().post("/", REMOTE_ADDR=address)))


def test_allow_adds_a_canonical_rule_owned_by_the_superadmin(root):
    assert "Allowed 198.51.100.0/24" in run("--allow", "198.51.100.9/24")
    rule = IPAccessRule.objects.get()
    assert rule.action == "allow" and rule.created_by.account_kind == "platform"
    assert AuditLog.objects.filter(action="platform.ip_rule_saved", meta__via="host_command").exists()
    IPAccessRule.objects.filter(pk=rule.pk).update(action="deny")
    run("--allow", "198.51.100.0/24")
    assert IPAccessRule.objects.get().action == "allow"


def test_allow_refuses_nonsense_and_a_deployment_without_a_superadmin():
    with pytest.raises(CommandError):
        run("--allow", "not-a-network")
    User.objects.filter(account_kind="platform").update(is_active=False)
    with pytest.raises(CommandError, match="no platform superadmin"):
        run("--allow", "198.51.100.9")


def test_unblock_one_address_or_all():
    _block("203.0.113.5")
    _block("203.0.113.6")
    assert "Unblocked 1" in run("--unblock", "203.0.113.5")
    assert list(IPAutoBlock.objects.values_list("network", flat=True)) == ["203.0.113.6/32"]
    assert "Unblocked 1" in run("--unblock", "all")
    assert not IPAutoBlock.objects.exists()
    assert AuditLog.objects.filter(action="auth.ip_unblocked").count() == 2
    with pytest.raises(CommandError):
        run("--unblock", "nope")


def test_list_shows_rules_and_active_blocks_only(root):
    IPAccessRule.objects.create(cidr="198.51.100.0/24", action="deny", note="bots", created_by=root)
    _block("203.0.113.7")
    IPAutoBlock.objects.create(ip_key="x" * 64, network="203.0.113.99/32",
                               blocked_until=timezone.now() - timedelta(minutes=1))
    out = run("--list")
    assert "198.51.100.0/24" in out and "bots" in out and "203.0.113.7/32" in out
    assert "203.0.113.99" not in out
