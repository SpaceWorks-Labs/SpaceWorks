"""The /control/ POST returns the bound quota form, preserving the exact API code."""
import socket

import pytest
from django.db import connection, connections
from django.test import Client
from django.urls import reverse

from tests.accounts.reauth_helpers import force_recent_control_login
from tests.limits_0120.admin_capacity_helpers_cx7 import bound_form, form_errors, prepare, row_for
from tests.makerspaces.test_control_capacity_cx7 import CASES, expected_error, used
from tests.r2_superadmin_local.helpers import superadmin
from tests.return_helpers import make_space

pytestmark = pytest.mark.django_db


@pytest.mark.parametrize("key", CASES)
def test_control_add_post_at_max_returns_exact_form_error(key, client, settings, monkeypatch):
    settings.MANAGED_PLANS_ENABLED = False
    space = make_space("cx7-control-post")
    actor = superadmin("cx7-control-post-root")
    force_recent_control_login(client, actor)
    prepare(key, space)
    space.resource_limit_overrides = {key: 1}
    space.save(update_fields=["resource_limit_overrides"])
    prototype = row_for(key, space, "Last")
    _, _, _, data = bound_form(prototype, actor)
    label = prototype._meta
    url = reverse(f"admin:{label.app_label}_{label.model_name}_add")
    page = client.get(url)
    assert page.status_code == 200
    inlines = {}
    for inline in page.context["inline_admin_formsets"]:
        prefix = inline.formset.prefix
        inlines.update({f"{prefix}-TOTAL_FORMS": "0", f"{prefix}-INITIAL_FORMS": "0",
                        f"{prefix}-MIN_NUM_FORMS": "0", f"{prefix}-MAX_NUM_FORMS": "1000"})
    if key == "webhook_endpoints":
        # Stub only the DNS response. URL parsing and public-address validation
        # execute normally for the real write-only credential field.
        monkeypatch.setattr("apps.integrations.webhook_validation.socket.getaddrinfo", lambda *args, **kwargs: [
            (socket.AF_INET, socket.SOCK_STREAM, 6, "", ("8.8.8.8", 443))])
        data["new_webhook_url"] = "https://example.test/hook"
    maximum = client.post(url, {**data, **inlines, "_save": "Save"})
    assert maximum.status_code == 302
    assert used(space, key) == 1
    for name in ("name", "label", "asset_tag"):
        if name in data:
            data[name] = "Excess"
    refused = client.post(url, {**data, **inlines, "_save": "Save"})
    assert refused.status_code == 200
    form = refused.context["adminform"].form
    error = expected_error(space, key)
    assert form_errors(form) == [(error.code, error.message)]
    assert used(space, key) == 1


@pytest.mark.django_db(transaction=True)
@pytest.mark.parametrize("key", CASES)
def test_two_control_posts_at_last_slot_have_one_exact_form_refusal(key, client, settings, monkeypatch):
    if connection.vendor != "postgresql":
        pytest.skip("Requires PostgreSQL row locks")
    settings.MANAGED_PLANS_ENABLED = False
    space = make_space("cx7-control-http-race")
    actor = superadmin("cx7-control-http-race-root")
    force_recent_control_login(client, actor)
    prepare(key, space)
    space.resource_limit_overrides = {key: 1}
    space.save(update_fields=["resource_limit_overrides"])
    prototype = row_for(key, space, "A")
    _, _, _, data = bound_form(prototype, actor)
    label = prototype._meta
    url = reverse(f"admin:{label.app_label}_{label.model_name}_add")
    page = client.get(url)
    assert page.status_code == 200
    for inline in page.context["inline_admin_formsets"]:
        prefix = inline.formset.prefix
        data.update({f"{prefix}-TOTAL_FORMS": "0", f"{prefix}-INITIAL_FORMS": "0",
                     f"{prefix}-MIN_NUM_FORMS": "0", f"{prefix}-MAX_NUM_FORMS": "1000"})
    if key == "webhook_endpoints":
        monkeypatch.setattr("apps.integrations.webhook_validation.socket.getaddrinfo", lambda *args, **kwargs: [
            (socket.AF_INET, socket.SOCK_STREAM, 6, "", ("8.8.8.8", 443))])
        data["new_webhook_url"] = "https://example.test/hook"
    second = dict(data)
    for name in ("name", "label", "asset_tag"):
        if name in second:
            second[name] = "B"
    # Each thread uses a separate HTTP client with the already verified control
    # session. Permissions, source gates, forms, inlines and saves all run normally.
    from conftest import _BoundedThreadPoolExecutor as ThreadPoolExecutor
    from threading import Barrier
    from django.db import close_old_connections
    barrier = Barrier(2)
    def post(body):
        close_old_connections()
        try:
            if connection.vendor == "postgresql":
                with connection.cursor() as cursor:
                    cursor.execute("SET lock_timeout = '5s'")
            caller = Client()
            caller.cookies = client.cookies.copy()
            barrier.wait(timeout=15)
            response = caller.post(url, body)
            if response.status_code == 200:
                return response.status_code, form_errors(response.context["adminform"].form)
            return response.status_code, []
        finally:
            connections.close_all()
    with ThreadPoolExecutor(max_workers=2) as pool:
        futures = [pool.submit(post, body) for body in (data, second)]
        results = [future.result(timeout=30) for future in futures]
    error = expected_error(space, key)
    assert sorted(results) == [(200, [(error.code, error.message)]), (302, [])]
    assert used(space, key) == 1
