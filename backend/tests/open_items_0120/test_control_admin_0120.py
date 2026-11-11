"""/control/ made proper for 0.12.0 (owner 2026-11-11: "django admin panel make it proper", "proper grouping").

Pins: the fourteen groups and their order (the React platform console mirrors them), every
registered model reachable from exactly one group or the internal-records list, every list
renders for a superadmin and refuses anyone else, read-only records stay read-only, no list
shows a secret, record pages show secrets only as set/not set and leave personal fields out,
and the home page carries the group map, backups and limits panels.
"""

import pytest
from django.contrib import admin
from django.test import Client, RequestFactory
from django.urls import NoReverseMatch, reverse

from apps.accounts.models import User
from config.admin_display import is_secret_name, tone_for
from config.admin_records import ControlRecordAdmin, record_fields
from config.control_catalog import GROUPS, HIDDEN_MODELS, SECTIONS
from config.unfold import UNFOLD
from tests.accounts.mfa_helpers import force_mfa_login
from tests.return_helpers import make_space, make_user

GROUP_ORDER = [
    "Overview", "Spaces", "People & roles", "Inventory", "Machines", "Events", "Bookings", "Shop", "Money",
    "Messaging & notifications", "Integrations & analytics", "Limits & hosting", "Data & recovery",
    "Security & audit",
]
IMMUTABLE = ("audit.auditlog", "evidence.evidencephoto", "boxes.qrscanevent", "boxes.boxscan",
             "payments.payment", "payments.manualsettlement", "payments.refund")


def superadmin(username="control-0120-root"):
    return make_user(username, role=User.Role.SUPERADMIN, access_status=User.AccessStatus.ACTIVE,
                     is_staff=True, is_superuser=True)


def control(username="control-0120-root"):
    client = Client(HTTP_HOST="localhost")
    force_mfa_login(client, superadmin(username))
    return client


def admin_request(user):
    request = RequestFactory().get("/control/")
    request.user = user
    return request


def registry():
    return {model._meta.label_lower: model_admin for model, model_admin in admin.site._registry.items()}


# --- grouping -------------------------------------------------------------------------------

def test_the_groups_are_the_decided_fourteen_in_order_each_with_an_icon_and_a_description():
    assert [str(title) for _key, title, _icon, _description in GROUPS] == GROUP_ORDER
    assert [str(group["title"]) for group in UNFOLD["SIDEBAR"]["navigation"]] == GROUP_ORDER
    for section in SECTIONS:
        assert section.icon and len(str(section.description)) >= 20, section.key
        assert "tenant" not in str(section.title).lower() and "tenant" not in str(section.description).lower()


def test_every_registered_model_is_in_exactly_one_group_or_the_internal_list():
    registered = set(registry())
    placed = [entry.key for section in SECTIONS for entry in section.entries if entry.is_model]
    assert len(placed) == len(set(placed))
    assert registered - set(placed) - HIDDEN_MODELS == set()
    assert not set(placed) & HIDDEN_MODELS
    assert HIDDEN_MODELS <= registered
    assert UNFOLD["SIDEBAR"]["show_all_applications"] is True  # internal records stay reachable


def test_no_user_facing_title_says_tenant():
    for section in SECTIONS:
        for entry in section.entries:
            assert "tenant" not in str(entry.title).lower(), entry.key
            assert "tenant" not in str(entry.help).lower(), entry.key


@pytest.mark.django_db
def test_hidden_internal_records_are_read_only():
    request = admin_request(superadmin("control-0120-hidden"))
    for label in HIDDEN_MODELS:
        model_admin = registry()[label]
        assert model_admin.has_view_permission(request), label
        assert not model_admin.has_add_permission(request), label
        assert not model_admin.has_change_permission(request), label
        assert not model_admin.has_delete_permission(request), label


# --- every list renders for the superadmin, and only for the superadmin ----------------------

@pytest.mark.django_db
def test_every_registered_changelist_renders_for_a_superadmin(settings, monkeypatch):
    settings.MANAGED_PLANS_ENABLED = True
    monkeypatch.setattr("apps.makerspaces.domain_verification.is_self_host", lambda: False)
    client = control("control-0120-lists")
    request = admin_request(User.objects.get(username="control-0120-lists"))
    failures = []
    for model, model_admin in admin.site._registry.items():
        if not model_admin.has_view_permission(request):
            continue
        opts = model._meta
        try:
            url = reverse(f"admin:{opts.app_label}_{opts.model_name}_changelist")
        except NoReverseMatch:
            continue
        status = client.get(url).status_code
        if status != 200:
            failures.append((opts.label_lower, status))
    assert failures == []


@pytest.mark.django_db
def test_the_per_space_limits_page_and_home_render():
    client = control("control-0120-pages")
    space = make_space("control-0120-limits")
    space.resource_limit_overrides = {"products": 1}
    space.save(update_fields=["resource_limit_overrides"])
    limits = client.get(reverse("admin:managed_hosting_spacehostingtype_limits"))
    assert limits.status_code == 200 and b'data-testid="control-limits"' in limits.content
    assert space.name.encode() in limits.content
    assert limits["Cache-Control"] == "private, no-store"
    home = client.get(reverse("admin:index")).content.decode()
    for marker in ('data-testid="control-group-map"', 'data-testid="control-home-backups"',
                   'data-testid="control-home-limits"', 'data-testid="control-internal-records"'):
        assert marker in home, marker
    for title in GROUP_ORDER[1:]:
        assert title.replace("&", "&amp;") in home, title


@pytest.mark.django_db
def test_a_non_superadmin_never_reaches_a_list_and_anonymous_is_sent_to_sign_in():
    url = reverse("admin:payments_payment_changelist")
    staff = make_user("control-0120-staff", is_staff=True)
    client = Client(HTTP_HOST="localhost")
    client.force_login(staff)
    assert client.get(url).status_code in (302, 403)
    assert client.get(reverse("admin:managed_hosting_spacehostingtype_limits")).status_code in (302, 403)
    anonymous = Client(HTTP_HOST="localhost").get(url)
    assert anonymous.status_code == 302 and "login" in anonymous["Location"]
    request = admin_request(staff)
    assert not any(model_admin.has_module_permission(request) for model_admin in admin.site._registry.values()
                   if isinstance(model_admin, ControlRecordAdmin))


# --- read-only and secrets ----------------------------------------------------------------------

@pytest.mark.django_db
def test_immutable_and_record_admins_expose_no_add_change_or_delete():
    request = admin_request(superadmin("control-0120-immutable"))
    by_label = registry()
    for label in IMMUTABLE:
        model_admin = by_label[label]
        assert not model_admin.has_add_permission(request), label
        assert not model_admin.has_change_permission(request), label
        assert not model_admin.has_delete_permission(request), label
    for label, model_admin in by_label.items():
        if isinstance(model_admin, ControlRecordAdmin):
            assert not model_admin.has_add_permission(request), label
            assert not model_admin.has_change_permission(request), label
            assert not model_admin.has_delete_permission(request), label
            assert "delete_selected" not in model_admin.get_actions(request), label


@pytest.mark.django_db
def test_no_list_shows_a_secret_field():
    request = admin_request(superadmin("control-0120-secrets"))
    offenders = []
    for model, model_admin in admin.site._registry.items():
        for name in model_admin.get_list_display(request):
            if not isinstance(name, str):
                continue
            try:
                field = model._meta.get_field(name)
            except Exception:  # noqa: BLE001 - a display method, not a stored field
                continue
            if is_secret_name(field.name) and field.get_internal_type() != "BooleanField":
                offenders.append(f"{model._meta.label_lower}.{name}")
    assert offenders == []


@pytest.mark.django_db
def test_a_record_page_shows_a_secret_only_as_set_and_never_its_value():
    from apps.analytics.models import AnalyticsConnection

    space = make_space("control-0120-analytics")
    row = AnalyticsConnection.objects.create(makerspace=space, metabase_url="https://bi.example.test",
                                             embed_secret="embed-sekrit-value", grafana_token="grafana-sekrit-value")
    client = control("control-0120-analytics-root")
    for url in (reverse("admin:analytics_analyticsconnection_changelist"),
                reverse("admin:analytics_analyticsconnection_change", args=[row.pk])):
        body = client.get(url).content.decode()
        assert "embed-sekrit-value" not in body and "grafana-sekrit-value" not in body
        assert "Set" in body


def test_record_pages_leave_personal_fields_out_and_show_accounts_by_id():
    from apps.payments.donations.models_donations import Donation
    from apps.shop.models_orders import ShopOrder

    donation = record_fields(Donation, ("tax_receipt", "tax_detail"))
    for name in ("donor_name", "donor_email", "donor_note", "tax_receipt", "tax_detail", "access_secret"):
        assert name not in donation, name
    assert "account__donor" in donation and "secret__access_secret" in donation
    order = record_fields(ShopOrder)
    assert "guest_name" not in order and "guest_email" not in order
    assert "secret__pickup_code" in order and "secret__status_secret" in order


def test_status_badges_carry_a_word_and_a_tone():
    assert tone_for("paid") == "success"
    assert tone_for("failed") == "danger"
    assert tone_for("pending") == "warning"
    assert tone_for("something_else") == "neutral"


@pytest.mark.django_db
def test_lists_join_the_foreign_keys_they_show():
    request = admin_request(superadmin("control-0120-joins"))
    model_admin = registry()["bookings.booking"]
    assert "space" in (model_admin.get_list_select_related(request) or ())
    payments = registry()["payments.payment"]
    assert payments.get_list_filter(request)[0] == "makerspace"
