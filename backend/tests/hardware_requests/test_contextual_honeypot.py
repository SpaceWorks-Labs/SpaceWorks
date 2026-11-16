from unittest.mock import Mock

import pytest
from rest_framework.test import APIRequestFactory, force_authenticate

from apps.hardware_requests import contextual_equipment_views as views
from tests.return_helpers import make_space, make_user


@pytest.mark.django_db
def test_filled_honeypot_returns_decoy_without_intake_or_notifications(monkeypatch):
    maker = make_space("contextual-honeypot")
    maker.public_site_enabled = maker.public_inventory_enabled = True
    actor = make_user("contextual-honeypot-actor")
    monkeypatch.setattr(views, "get_public_makerspace", lambda _: maker)
    monkeypatch.setattr(views, "require_module_for_servable", lambda *_: None)
    monkeypatch.setattr(views, "module_enabled", lambda *_: False)
    monkeypatch.setattr(views, "require_active_account", lambda *_: None)
    submit = Mock(side_effect=AssertionError("intake must not run"))
    monkeypatch.setattr(views, "_submit", submit)
    request = APIRequestFactory().post("/api/v1/public/contextual-honeypot/requests/contextual",
                                       {"website": "spam"}, format="json")
    force_authenticate(request, user=actor)
    response = views.ContextualSelfView.as_view()(request, makerspace_slug=maker.slug)
    assert response.status_code == 201
    assert response.data["kind"] == "request"
    assert response.data["replayed"] is False
    submit.assert_not_called()
