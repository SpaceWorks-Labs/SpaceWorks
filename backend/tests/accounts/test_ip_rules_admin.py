"""S-C: platform IP rules in /control/ (superadmin whitelist, deny-self guard, cache, unblock)."""

from datetime import timedelta

import pytest
from django.contrib import admin
from django.contrib.admin.helpers import ACTION_CHECKBOX_NAME
from django.test import Client, RequestFactory
from django.urls import reverse
from django.utils import timezone

from apps.accounts import ip_rules
from apps.accounts.admin_ip_access import IPAccessRuleForm, unblock
from apps.accounts.models import IPAccessRule, IPAutoBlock, User
from apps.accounts.reauthentication_control import CONTROL_AUTHORITY_MODELS
from apps.audit.models import AuditLog
from config.admin_scope_registry import GLOBAL_ADMIN_MODELS
from tests.accounts.reauth_helpers import force_recent_control_login

pytestmark = pytest.mark.django_db


@pytest.fixture
def root():
    return User.objects.create_user(username="root-ip", password="Root password 77!", account_kind="platform",
                                    role=User.Role.SUPERADMIN, is_superuser=True, is_staff=True)


@pytest.fixture(autouse=True)
def website_route(settings):
    # A non-loopback peer reaches /control/ only through the opt-in website route (#191).
    settings.CONTROL_PLANE_PROXY = True


def control(user):
    client = Client(REMOTE_ADDR="198.51.100.4")
    force_recent_control_login(client, user)
    return client


def test_models_are_global_superadmin_screens_behind_the_step_up():
    assert {"accounts.ipaccessrule", "accounts.ipautoblock"} <= GLOBAL_ADMIN_MODELS
    assert {"accounts.ipaccessrule", "accounts.ipautoblock"} <= CONTROL_AUTHORITY_MODELS
    assert IPAccessRule in admin.site._registry and IPAutoBlock in admin.site._registry


def test_axes_exempts_only_the_superadmin_from_an_allow_listed_address(root):
    person = User.objects.create_user(username="person-ip", password="Person password 33!")
    request = RequestFactory().post("/control/login/", REMOTE_ADDR="198.51.100.4")
    assert ip_rules.axes_whitelisted(request, {"username": root.username}) is False
    IPAccessRule.objects.create(cidr="198.51.100.0/24", action="allow", created_by=root)
    assert ip_rules.axes_whitelisted(request, {"username": root.username}) is True
    assert ip_rules.axes_whitelisted(request, {"username": person.username}) is False
    elsewhere = RequestFactory().post("/control/login/", REMOTE_ADDR="203.0.113.4")
    assert ip_rules.axes_whitelisted(elsewhere, {"username": root.username}) is False


def _form(data, editor):
    form_class = type("Form", (IPAccessRuleForm,), {"editor_address": ip_rules.parse_address(editor)})
    return form_class(data={"note": "", "expires_at": "", **data})


def test_a_deny_rule_covering_the_editor_is_refused_unless_an_allow_rule_covers_them(root):
    refused = _form({"cidr": "198.51.100.0/24", "action": "deny"}, "198.51.100.4")
    assert not refused.is_valid() and "lock you out" in str(refused.errors)
    elsewhere = _form({"cidr": "203.0.113.0/24", "action": "deny"}, "198.51.100.4")
    assert elsewhere.is_valid(), elsewhere.errors
    IPAccessRule.objects.create(cidr="198.51.100.4/32", action="allow", created_by=root)
    covered = _form({"cidr": "198.51.100.0/24", "action": "deny"}, "198.51.100.4")
    assert covered.is_valid(), covered.errors
    assert covered.cleaned_data["cidr"] == "198.51.100.0/24"


def test_cidr_is_canonical_and_validated(root):
    form = _form({"cidr": "203.0.113.77/24", "action": "allow"}, "198.51.100.4")
    assert form.is_valid() and form.cleaned_data["cidr"] == "203.0.113.0/24"
    assert not _form({"cidr": "nonsense", "action": "allow"}, "198.51.100.4").is_valid()


def test_the_rule_cache_is_dropped_on_save_and_delete(root):
    address = ip_rules.parse_address("203.0.113.9")
    assert ip_rules.decision(address) == (None, None)  # now cached empty
    rule = IPAccessRule.objects.create(cidr="203.0.113.0/24", action="deny", created_by=root)
    assert ip_rules.decision(address)[0] == "deny"
    rule.delete()
    assert ip_rules.decision(address) == (None, None)


def test_expired_rules_do_not_apply(root):
    IPAccessRule.objects.create(cidr="203.0.113.0/24", action="deny", created_by=root,
                                expires_at=timezone.now() - timedelta(seconds=1))
    assert ip_rules.decision(ip_rules.parse_address("203.0.113.9")) == (None, None)


def test_control_saves_and_deletes_rules_with_audit_rows(root):
    client = control(root)
    url = reverse("admin:accounts_ipaccessrule_add")
    response = client.post(url, {"cidr": "203.0.113.0/24", "action": "deny", "note": "stuffing", "expires_at": ""})
    assert response.status_code == 302, response.content[:2000]
    rule = IPAccessRule.objects.get()
    assert rule.created_by == root
    saved = AuditLog.objects.get(action="platform.ip_rule_saved")
    assert saved.meta["action"] == "deny" and "203.0.113" not in str(saved.meta)
    delete = client.post(reverse("admin:accounts_ipaccessrule_delete", args=[rule.pk]), {"post": "yes"})
    assert delete.status_code == 302 and not IPAccessRule.objects.exists()
    assert AuditLog.objects.filter(action="platform.ip_rule_deleted").count() == 1


def test_control_blocks_changelist_and_unblock_action(root):
    row = IPAutoBlock.objects.create(ip_key="k" * 64, network="203.0.113.5/32",
                                     blocked_until=timezone.now() + timedelta(hours=1))
    client = control(root)
    url = reverse("admin:accounts_ipautoblock_changelist")
    page = client.get(url)
    assert page.status_code == 200 and b"203.0.113.5/32" in page.content
    done = client.post(url, {"action": "unblock_selected", ACTION_CHECKBOX_NAME: [str(row.pk)], "index": "0"})
    assert done.status_code == 302 and not IPAutoBlock.objects.exists()
    audit = AuditLog.objects.get(action="auth.ip_unblocked")
    assert audit.actor == root and audit.meta["ip_key"] == "k" * 64


def test_unblock_helper_counts_and_audits_each_row():
    for index in range(2):
        IPAutoBlock.objects.create(ip_key=str(index) * 64, network=f"203.0.113.{index}/32",
                                   blocked_until=timezone.now() + timedelta(hours=1))
    assert unblock(None, IPAutoBlock.objects.all()) == 2
    assert AuditLog.objects.filter(action="auth.ip_unblocked").count() == 2


def test_auto_blocks_send_no_email(mailoutbox, settings):
    from django.test import RequestFactory as Factory

    from apps.accounts import ip_guard
    ip_guard.block(ip_guard.client_source(Factory().post("/", REMOTE_ADDR="203.0.113.50")))
    assert IPAutoBlock.objects.count() == 1 and mailoutbox == []
