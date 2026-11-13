"""Fix-URLs and the Stripe return URL point at the exact `/admin/settings/<section>` subpage."""
from types import SimpleNamespace

from apps.makerspaces.platform import staff_payment_settings_url
from apps.operations import platform_checks as checks


def _space(**extra):
    fields = {"frontend_domain": "", "frontend_domain_status": "", **extra}  # overrides replace the defaults
    return SimpleNamespace(name="Lab", slug="lab", pk=1, enabled_modules=["email"], **fields)


def test_domain_check_points_at_branding_and_email_at_integrations():
    domain = checks.domain_check({"space": _space(frontend_domain="x.example", frontend_domain_status="failed")}, None)
    assert domain[0]["fix_url"] == "/m/lab/admin/settings/branding"
    data = {"space": _space(), "health": {"email": {"status": "ok"}, "smtp": {"status": "error"}}}
    assert checks.email_check(data, None)[0]["fix_url"] == "/m/lab/admin/settings/integrations"


def test_stripe_connect_return_lands_on_the_money_page():
    url = staff_payment_settings_url(SimpleNamespace(frontend_domain="", frontend_domain_status="", slug="lab"), outcome="success")
    assert url.endswith("/m/lab/admin/settings/money?stripe_connect=success")
