"""Review regressions share the established presence and signed Meta fixtures."""
import pytest

from tests.p2_presence.conftest import lane
from tests.p2_wa_meta.conftest import wa


@pytest.fixture(autouse=True)
def no_external_delivery(monkeypatch):
    monkeypatch.setattr("apps.integrations.notification_outbox.enqueue", lambda *_: None)
    monkeypatch.setattr("apps.events.services.notify_event_lifecycle", lambda *_: None)

    def refused(*args, **kwargs):
        raise AssertionError("Review tests must not contact external services")

    monkeypatch.setattr("requests.sessions.Session.request", refused)
