"""#188 (regrouped for 0.12.0): the /control/ structure -- one catalogue, fourteen groups, help lines,
the home dashboard.

The pin the owner asked for is the first test: every registered admin model appears in
exactly ONE sidebar group, or in the catalogue's internal-records list. Adding an admin model
without a catalogue line fails it.
"""

from collections import Counter
from datetime import timedelta

import pytest
from django.contrib import admin
from django.contrib.admin.helpers import ACTION_CHECKBOX_NAME
from django.test import RequestFactory
from django.urls import reverse
from django.utils import timezone

from apps.accounts.models import User
from config.control_catalog import HIDDEN_MODELS, MODEL_ENTRIES, SECTION_TITLES, SECTIONS, help_for
from config.unfold import UNFOLD
from tests.accounts.mfa_helpers import force_mfa_login
from tests.return_helpers import make_product, make_space, make_user

EXPECTED_SECTIONS = [
    "Overview", "Spaces", "People & roles", "Inventory", "Machines", "Events", "Bookings", "Shop", "Money",
    "Messaging & notifications", "Integrations & analytics", "Limits & hosting", "Data & recovery",
    "Security & audit",
]
BROKEN_PLURALS = ("settingss", "boxs", "entrys", "identitys", "warrantys", "batchs", "leafs", "accountabilitys")


def sidebar_items():
    return [(group, item) for group in UNFOLD["SIDEBAR"]["navigation"] for item in group["items"]]


def superadmin(username="catalog-root"):
    return make_user(username, role=User.Role.SUPERADMIN, access_status=User.AccessStatus.ACTIVE,
                     is_staff=True, is_superuser=True)


def control(username="catalog-root"):
    from django.test import Client

    client = Client(HTTP_HOST="localhost")
    force_mfa_login(client, superadmin(username))
    return client


def test_every_registered_admin_model_appears_in_exactly_one_sidebar_section():
    registered = {model._meta.label_lower for model in admin.site._registry}
    placed = Counter(item["catalog_key"] for _group, item in sidebar_items() if "." in item["catalog_key"]
                     and ":" not in item["catalog_key"])
    assert {label for label, count in placed.items() if count > 1} == set()
    assert set(placed) & HIDDEN_MODELS == set()
    assert registered - set(placed) - HIDDEN_MODELS == set(), "add a line to config/control_catalog_entries*.py"
    assert set(placed) - registered == set(), "a catalogue line names a model that is not registered"
    assert HIDDEN_MODELS <= registered


def test_each_model_route_is_its_changelist_and_the_sections_are_the_decided_fourteen():
    assert [title for _key, title in SECTION_TITLES] == EXPECTED_SECTIONS
    assert [str(group["title"]) for group in UNFOLD["SIDEBAR"]["navigation"]] == EXPECTED_SECTIONS
    for _group, item in sidebar_items():
        key = item["catalog_key"]
        if key in MODEL_ENTRIES:
            app_label, model_name = key.split(".")
            assert item["route"] == f"admin:{app_label}_{model_name}_changelist"
        assert str(item["link"])  # resolves (a stale route would 500 the whole console)


def test_every_entry_has_a_plain_title_and_a_help_line():
    for section in SECTIONS:
        for entry in section.entries:
            assert entry.title and entry.title[0].isupper(), entry.key
            assert len(entry.help) >= 12 and entry.help.endswith("."), entry.key
            assert "_" not in entry.title, entry.key  # no raw model or field names


def test_no_registered_model_keeps_a_broken_english_plural():
    for model in admin.site._registry:
        assert not str(model._meta.verbose_name_plural).endswith(BROKEN_PLURALS), model._meta.label_lower


@pytest.mark.django_db
def test_managed_billing_shows_in_limits_only_when_the_limiter_is_on(settings, monkeypatch):
    limits = next(group for group in UNFOLD["SIDEBAR"]["navigation"] if group["section"] == "limits")
    plans = [item for item in limits["items"] if item["catalog_key"] in {
        "managed_hosting.hostingplan", "managed_hosting.spaceplanassignment", "managed_hosting.hostinginvoice"}]
    assert len(plans) == 3
    request = RequestFactory().get("/control/")
    request.user = superadmin()
    settings.MANAGED_PLANS_ENABLED = False
    assert not any(item["permission"](request) for item in plans)
    settings.MANAGED_PLANS_ENABLED = True
    monkeypatch.setattr("apps.makerspaces.domain_verification.is_self_host", lambda: False)
    assert all(item["permission"](request) for item in plans)


@pytest.mark.django_db
def test_every_sidebar_entry_is_superadmin_only():
    request = RequestFactory().get("/control/")
    request.user = make_user("catalog-staff", is_staff=True)
    assert not any(item["permission"](request) for _group, item in sidebar_items())


@pytest.mark.django_db
def test_a_model_list_and_form_open_with_their_help_line():
    client = control()
    space = make_space("catalog-help")
    listing = client.get(reverse("admin:makerspaces_makerspace_changelist"))
    assert listing.status_code == 200
    assert help_for("makerspaces.makerspace").encode() in listing.content
    form = client.get(reverse("admin:makerspaces_makerspace_change", args=[space.pk]))
    assert form.status_code == 200 and b'data-testid="control-model-help"' in form.content


@pytest.mark.django_db
def test_the_home_dashboard_lists_what_needs_attention_with_counts_only():
    from apps.accounts.models_ip_access import IPAutoBlock
    from apps.backup.models_drill import RestoreDrillReport
    from apps.integrations.models_email import EmailLog
    from apps.space_controls.models import SpaceControlState

    now = timezone.now()
    paused = make_space("catalog-paused")
    SpaceControlState.objects.create(makerspace=paused, suspended_at=now, suspension_reason="Dispute")
    IPAutoBlock.objects.create(network="203.0.113.0/24", ip_key="k" * 64, blocked_until=now + timedelta(hours=1))
    RestoreDrillReport.objects.create(makerspace=paused, makerspace_id_snapshot=paused.pk,
                                      archive_id_snapshot="00000000-0000-0000-0000-000000000001",
                                      outcome="failed", error_code="drill_failed")
    stuck = EmailLog.objects.create(to_email="private-person@example.test", subject="Hi", text_body="x", status="pending")
    EmailLog.objects.filter(pk=stuck.pk).update(created_at=now - timedelta(hours=2))

    response = control("catalog-home-root").get(reverse("admin:index"))
    body = response.content.decode()
    assert response.status_code == 200 and 'data-testid="control-home"' in body
    for label in ("Paused spaces", "Networks blocked now", "Restore drills failed in the last 30 days",
                  "Messages stuck for more than 30 minutes", "Quick links", "Spaces and accounts"):
        assert label in body, label
    assert "private-person@example.test" not in body and "Dispute" not in body


@pytest.mark.django_db
def test_the_home_never_computes_the_overview_inline(settings, monkeypatch):
    settings.CELERY_TASK_ALWAYS_EAGER = True
    monkeypatch.setattr("apps.operations.platform_overview.build_platform_overview",
                        lambda *args, **kwargs: pytest.fail("the overview ran inside the page view"))
    from config.control_dashboard import overview_totals
    assert overview_totals()["status"] == "not_computed"


@pytest.mark.django_db
def test_a_dangerous_action_asks_first_and_the_confirmed_post_runs_it():
    from apps.boxes.models import QrCode

    client = control("catalog-confirm-root")
    space = make_space("catalog-confirm")
    product = make_product(space, name="Probe")
    qr = QrCode.objects.create(makerspace=space, target_type=QrCode.TargetType.PRODUCT, target_id=product.id)
    url = reverse("admin:boxes_qrcode_changelist")
    data = {"action": "revoke_selected", ACTION_CHECKBOX_NAME: [str(qr.pk)], "index": "0"}
    first = client.post(url, data)
    qr.refresh_from_db()
    assert first.status_code == 200 and b'data-testid="control-confirm-action"' in first.content
    assert b"cannot be undone" in first.content and qr.status == QrCode.Status.ACTIVE
    client.post(url, {**data, "control_confirmed": "yes"}, follow=True)
    qr.refresh_from_db()
    assert qr.status == QrCode.Status.REVOKED


@pytest.mark.django_db
def test_every_registered_dangerous_action_exists_and_is_confirmed():
    from config.admin_confirm import DANGEROUS_ACTIONS, ConfirmDangerousActionsMixin

    request = RequestFactory().get("/control/")
    request.user = superadmin("catalog-actions-root")
    by_label = {model._meta.label_lower: model_admin for model, model_admin in admin.site._registry.items()}
    for key in DANGEROUS_ACTIONS:
        label, action = key.rsplit(".", 1)
        model_admin = by_label[label]
        assert isinstance(model_admin, ConfirmDangerousActionsMixin), key
        assert action in model_admin.get_actions(request), key
        assert str(model_admin.get_actions(request)[action][2]).endswith(("(cannot be undone)", "(asks you to confirm)"))
