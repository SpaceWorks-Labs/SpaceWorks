"""#187A: the managed-hosting limiter. The key test: switch off -> zero visible or enforced change."""

from datetime import date, timedelta
from unittest import mock

import pytest
from django.utils import timezone
from rest_framework.exceptions import ValidationError

from apps.audit.models import AuditLog
from apps.makerspaces import limits
from apps.makerspaces.module_install import ModuleInstallError, install_module, uninstall_module
from apps.managed_hosting import billing, online, plans, trials
from apps.managed_hosting.models import HostingInvoice, HostingPlan, PlatformHostingBillingSettings
from apps.managed_hosting.usage import plan_usage
from apps.space_controls import health
from apps.space_controls.models import SpaceControlState

from .helpers import api, manager, member, space, superadmin

pytestmark = pytest.mark.django_db
PLATFORM = "/api/v1/admin/platform"


@pytest.fixture
def world(managed):
    lab = space()
    root, boss = superadmin(), manager(lab)
    plan = HostingPlan.objects.create(key="community", name="Community", limits={"members": 5, "events_monthly": 1},
                                      allowed_modules=["events", "bookings"], trial_days=14)
    return type("World", (), dict(lab=lab, root=root, boss=boss, plan=plan, settings=managed))


def assign(world, trial_days=0):
    world.settings.MANAGED_PLANS_ENABLED = True
    row = plans.assign(world.root, world.lab.pk, world.plan.pk, trial_days=trial_days)
    return row


def test_switch_off_changes_nothing_visible_or_enforced(world):
    from apps.managed_hosting.models import SpacePlanAssignment

    world.settings.MANAGED_PLANS_ENABLED = False
    SpacePlanAssignment.objects.create(makerspace=world.lab, plan=world.plan)  # stale row from a past "on"
    # #236 addendum: the built-in values are suggestions only; nothing set means unlimited.
    assert limits.resource_limit(world.lab, "members") is None
    config = api().get("/api/v1/config").json()
    assert "managed_plans" not in config
    assert "plan" not in health.card(world.lab)
    for path in ("/hosting-plans", "/hosting-invoices", "/hosting-billing-settings", f"/spaces/{world.lab.pk}/plan"):
        assert api(world.root).get(PLATFORM + path).status_code == 404
    # Decision 236: the Space Manager's usage page is not plan-gated (SpacePlanUsageView plans_required=False);
    # an OWN space (explicit type: the suite's conftest makes an absent row hosted) answers with no plan, not 404.
    from apps.managed_hosting.hosting_type import OWN, set_type
    set_type(world.root, world.lab, OWN)
    usage = api(world.boss).get(f"/api/v1/admin/makerspace/{world.lab.pk}/hosting-plan")
    assert usage.status_code == 200 and usage.json()["plan"] is None and usage.json()["hosted"] is False
    uninstall_module(world.lab, "shop")
    assert install_module(world.lab, "shop") == ["shop"]  # not refused by the plan's module list
    with mock.patch("apps.managed_hosting.enforcement.monthly_used") as counted:
        limits.check_quota(world.lab, "events")
        counted.assert_not_called()


def test_plans_work_on_a_plain_install_when_the_switch_is_on(world):
    """#234: one deployment mode. The env override (or the console switch) turns plans on without a platform domain."""
    world.settings.MANAGED_PLANS_ENABLED = True
    world.settings.PLATFORM_DOMAIN_SUFFIX = ""
    assert "managed_plans" in api().get("/api/v1/config").json()
    assert api(world.root).get(PLATFORM + "/hosting-plans").status_code == 200


def test_plan_limits_warn_at_80_and_stop_at_100(world):
    assign(world)
    for index in range(4):
        member(world.lab, f"m{index}")
    usage = {row["key"]: row for row in plan_usage(world.lab)["resources"]}
    assert usage["members"]["used"] == 4 and usage["members"]["level"] == "warning"
    member(world.lab, "m4")
    assert {row["key"]: row for row in plan_usage(world.lab)["resources"]}["members"]["level"] == "limit"
    with pytest.raises(ValidationError) as refused:
        limits.check_quota(world.lab, "members")
    assert "Community plan" in str(refused.value.detail["limit"]) and "code" in refused.value.detail
    response = api(world.boss).get(f"/api/v1/admin/makerspace/{world.lab.pk}/hosting-plan").json()
    assert response["plan"]["name"] == "Community" and response["warnings"]


def test_override_beats_plan_and_monthly_events(world):
    assign(world)
    world.lab.resource_limit_overrides = {"members": 50}
    world.lab.save(update_fields=["resource_limit_overrides"])
    assert limits.resource_limit(world.lab, "members") == 50
    with mock.patch("apps.managed_hosting.enforcement.monthly_used", return_value=1):
        with pytest.raises(ValidationError) as refused:
            limits.check_quota(world.lab, "events")
    assert "new events this month" in str(refused.value.detail["limit"])


def test_allowed_modules(world):
    assign(world)
    uninstall_module(world.lab, "shop")
    with pytest.raises(ModuleInstallError):
        install_module(world.lab, "shop")


def test_trial_reminders_then_read_only_then_plan_lifts_it(world, mailbox, django_capture_on_commit_callbacks):
    row = assign(world, trial_days=10)
    now = timezone.now()
    with django_capture_on_commit_callbacks(execute=True):
        trials.sweep(row.trial_ends_at - timedelta(days=6))
    assert "trial ends in 6 days" in mailbox[-1].subject
    with django_capture_on_commit_callbacks(execute=True):
        assert trials.sweep(row.trial_ends_at + timedelta(minutes=1))["expired"] == 1
    state = SpaceControlState.objects.get(makerspace=world.lab)
    assert state.read_only_source == "trial_expired" and state.read_only_at is not None
    assert AuditLog.objects.filter(action="managed_hosting.trial_expired").exists()
    plans.assign(world.root, world.lab.pk, world.plan.pk, trial_days=0)
    state.refresh_from_db()
    assert state.read_only_at is None and now


def invoice(world, due=None):
    return billing.create_invoice(world.root, {"makerspace_id": world.lab.pk, "amount_minor": 5000,
                                               "currency": "usd", "description": "Hosting, November",
                                               "due_on": due or date.today()})


def test_recorded_billing_and_enforcement_only_when_enabled(world, django_capture_on_commit_callbacks):
    world.settings.MANAGED_PLANS_ENABLED = True
    row = invoice(world, due=date.today() - timedelta(days=30))
    assert row.number.startswith("SWH-") and row.currency == "USD"
    assert billing.enforce_overdue() == 0  # auto-enforcement is off by default
    settings_row = PlatformHostingBillingSettings.load()
    settings_row.auto_enforce_enabled, settings_row.grace_days = True, 14
    settings_row.save()
    assert billing.enforce_overdue() == 1
    assert SpaceControlState.objects.get(makerspace=world.lab).read_only_source == "payment_overdue"
    with django_capture_on_commit_callbacks(execute=True):
        billing.record_payment(world.root, row.pk, method="bank_transfer", reference="TX-1",
                               received_on=date.today())
    row.refresh_from_db()
    assert row.status == "paid" and row.receipts.get().reference == "TX-1"
    assert SpaceControlState.objects.get(makerspace=world.lab).read_only_at is None
    second = invoice(world)
    billing.void(world.root, second.pk, "Issued twice")
    assert HostingInvoice.objects.get(pk=second.pk).status == "void"


def test_online_checkout_with_mocks(world, django_capture_on_commit_callbacks):
    world.settings.MANAGED_PLANS_ENABLED = True
    row = invoice(world)
    url = f"/api/v1/admin/makerspace/{world.lab.pk}/hosting-invoices/{row.pk}/checkout"
    assert api(world.boss).post(url, {}, format="json").status_code == 404  # second switch off
    world.settings.MANAGED_BILLING_ONLINE_ENABLED = True
    settings_row = PlatformHostingBillingSettings.load()
    settings_row.provider = "stripe"
    settings_row.set_secret("stripe_secret_key", "sk_test_x")
    settings_row.set_secret("stripe_webhook_secret", "whsec_x")
    settings_row.save()
    with mock.patch("stripe.checkout.Session.create", return_value={"id": "cs_1", "url": "https://pay.test/cs_1"}):
        response = api(world.boss).post(url, {}, format="json")
    assert response.status_code == 200 and response.json() == {"url": "https://pay.test/cs_1"}
    event = {"type": "checkout.session.completed", "data": {"object": {
        "id": "cs_1", "payment_status": "paid", "metadata": {"hosting_invoice_id": str(row.pk)},
        "amount_total": 5000, "currency": "usd", "payment_intent": "pi_1"}}}
    with mock.patch("stripe.Webhook.construct_event", return_value=event):
        with django_capture_on_commit_callbacks(execute=True):
            for _ in range(2):  # a replayed callback settles once
                assert api().post("/api/v1/managed-hosting/webhooks/stripe", b"{}", content_type="application/json",
                                  HTTP_STRIPE_SIGNATURE="t=1,v1=x").status_code == 200
    row.refresh_from_db()
    assert row.status == "paid" and row.receipts.count() == 1
    wrong = invoice(world)
    event["data"]["object"].update(metadata={"hosting_invoice_id": str(wrong.pk)}, amount_total=1)
    assert online.settle({"invoice_id": str(wrong.pk), "amount_minor": 1, "currency": "USD",
                          "reference": "pi_2", "method": "online_stripe"}) is False
    assert HostingInvoice.objects.get(pk=wrong.pk).status == "open"


def test_platform_routes_are_superadmin_only_and_audited(world):
    world.settings.MANAGED_PLANS_ENABLED = True
    assert api(world.boss).get(PLATFORM + "/hosting-plans").status_code == 403
    created = api(world.root).post(PLATFORM + "/hosting-plans", {
        "key": "pro", "name": "Pro", "limits": {"members": 500, "sms_monthly": 100}, "allowed_modules": []},
        format="json")
    assert created.status_code == 201, created.content
    assert api(world.root).post(PLATFORM + "/hosting-plans", {"key": "bad", "name": "Bad",
                                                              "limits": {"nonsense": 1}}, format="json").status_code == 400
    put = api(world.root).put(f"{PLATFORM}/spaces/{world.lab.pk}/plan", {"plan_id": created.json()["id"]},
                              format="json")
    assert put.status_code == 200 and put.json()["plan"]["key"] == "pro"
    patch = api(world.root).patch(PLATFORM + "/hosting-billing-settings",
                                  {"stripe_secret_key": "sk_live_y", "grace_days": 7}, format="json").json()
    assert patch["stripe_secret_key_set"] is True and "stripe_secret_key" not in patch
    assert PlatformHostingBillingSettings.load().stripe_secret_key.startswith("fernet:")
    actions = set(AuditLog.objects.values_list("action", flat=True))
    assert {"managed_hosting.plan_created", "managed_hosting.plan_assigned",
            "managed_hosting.billing_settings_updated"} <= actions
