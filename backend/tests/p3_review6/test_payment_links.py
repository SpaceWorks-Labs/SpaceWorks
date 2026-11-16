from types import SimpleNamespace as Bag

import pytest
from django.utils import timezone

from apps.integrations.notification_links import external_links, local_link
from apps.makerspaces.website_directory import public_url
from apps.payments.notifications_p2 import document_body, rendered

pytestmark = pytest.mark.django_db


@pytest.mark.parametrize("archived", [False, True])
@pytest.mark.parametrize("custom", [False, True])
def test_document_navigation_survives_archival_in_every_transport(world, settings, archived, custom):
    settings.PUBLIC_APP_BASE_URL = "https://central.example.test"
    space = world.space
    if custom:
        space.frontend_domain, space.frontend_domain_status = "custom.example.test", "verified"
    if archived:
        space.archived_at = timezone.now()
    document = Bag(kind="receipt", makerspace=space, get_kind_display=lambda: "Receipt", number="R<1>",
                   currency="usd", amount="12.50")
    url = ("https://central.example.test/member/archived" if archived
           else public_url(space, "member", "").rstrip("/"))
    local = "/member/archived" if archived else local_link(space, "member")
    content = document_body(document)
    assert content["link"] == local
    for result in (content, external_links(space, content)):
        assert url in result["text"] and url in result["html"]
        assert "USD 12.50" in result["text"]
        assert "R&lt;1&gt;" in result["html"] and "R<1>" not in result["html"]
        if archived:
            assert "custom.example.test" not in str(result)
            assert f"/m/{space.slug}/member" not in str(result)
    assert external_links(space, content)["link"] == url


@pytest.mark.parametrize("event", ["charge_raised", "payment_received", "refund_issued"])
@pytest.mark.parametrize("archived", [False, True])
def test_all_owner_ledger_notices_use_recoverable_navigation(world, settings, event, archived):
    settings.PUBLIC_APP_BASE_URL = "https://central.example.test"
    space = world.space
    space.frontend_domain, space.frontend_domain_status = "custom.example.test", "verified"
    if archived:
        space.archived_at = timezone.now()
    payment = Bag(pk=1, status="paid_offline", makerspace=space, amount="12.50", currency="usd", due_at=None)
    content = rendered(payment, event, "requester")
    url = ("https://central.example.test/member/archived" if archived else "https://custom.example.test/member")
    assert content["link"] == ("/member/archived" if archived else "/member")
    assert external_links(space, content)["link"] == url
    assert url in external_links(space, content)["text"]
