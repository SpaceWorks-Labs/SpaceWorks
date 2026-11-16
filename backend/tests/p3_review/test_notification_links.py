from types import SimpleNamespace

import pytest
from django.utils import timezone

from apps.bookings.notifications import staff_content
from apps.events.notification_envelopes import _staff_link
from apps.integrations.notification_links import external_links
from apps.inventory.notifications_p2 import notify_watch
from apps.operations.notifications_p2 import staff_link
from tests.return_helpers import make_space

pytestmark = pytest.mark.django_db


@pytest.mark.parametrize("status,domain,base", [
    ("pending", "custom.example", "https://central.example/m/review-links"),
    ("verified", "custom.example", "https://custom.example"),
    ("pending", "", "https://central.example/m/review-links"),
])
def test_staff_and_item_links_use_canonical_tenant_routes(settings, monkeypatch, status, domain, base):
    settings.PUBLIC_APP_BASE_URL = "https://central.example/"
    home = make_space("review-links")
    home.frontend_domain, home.frontend_domain_status = domain, status
    local = "" if status == "verified" and domain else "/m/review-links"
    for tab in ("payments", "stocktake", "devices", "reports"):
        assert staff_link(home, tab) == f"{local}/admin/{tab}"
        assert external_links(home, {"link": staff_link(home, tab)})["link"] == f"{base}/admin/{tab}"
    assert _staff_link(home, SimpleNamespace(pk=42)) == f"{local}/admin/events?event=42"
    monkeypatch.setattr("apps.bookings.notifications.render", lambda *_: {"subject": "Update", "text_body": "Body"})
    booking = SimpleNamespace(space=SimpleNamespace(makerspace=home), space_id=8, pk=9, status="pending")
    assert staff_content(booking, "created", {})["link"] == f"{local}/admin/bookings?view=requests&status=pending"
    captured = []
    monkeypatch.setattr("apps.inventory.notifications_p2.fanout", lambda **kwargs: captured.append(kwargs))
    watch = SimpleNamespace(pk=1, makerspace=home, product_id=73, user=SimpleNamespace(pk=2),
        created_at=timezone.now(), ready_at=timezone.now())
    notify_watch(watch, SimpleNamespace(title="Available", body="A tool is back"))
    assert captured[0]["own"]["link"] == f"{local}/items/73"
    assert external_links(home, captured[0]["own"])["link"] == f"{base}/items/73"
