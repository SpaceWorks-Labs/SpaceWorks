from tests.events.website_helpers import make_page, make_session
from unittest.mock import Mock

import pytest
from rest_framework.exceptions import PermissionDenied

from apps.accounts.models import User
from apps.audit.models import AuditLog
from apps.events import event_authority, services, services_website
from apps.events.models import EventSeries
from apps.events.models_website import EventPage, EventPageAsset, EventSession
from apps.events.services_website_assets import delete_asset, upload_asset
from apps.events.website_projection import project
from tests.events.website_helpers import website_fixture

pytestmark = pytest.mark.django_db(transaction=True)


@pytest.mark.parametrize("change", [{"is_active": False}, {"access_status": "suspended"}])
@pytest.mark.parametrize("kind", ["event", "series"])
@pytest.mark.parametrize("operation", ["save", "release", "delay", "upload", "delete"])
def test_website_writes_reject_stale_authenticated_actor(change, kind, operation):
    space, actor, target, page, _ = website_fixture()
    if kind == "series":
        start = target.starts_at
        target = EventSeries.objects.create(
            makerspace=space, title="Series", recurrence_timezone="UTC",
            dtstart_local_date=start.date(), dtstart_local_time=start.time(),
            recurrence_rule="FREQ=DAILY;COUNT=2", duration_minutes=120, status="published",
        )
        page = make_page(makerspace=space, series=target, released=True)
    from apps.events.website_projection import window
    start, end = window(target)
    make_session(page=page, slug="talk", title="Talk", starts_at=start, ends_at=end)
    asset = EventPageAsset.objects.create(page=page, object_key="private-asset", size_bytes=4, alt_text="Photo")
    data = project(target)
    file = Mock()
    # The request still holds the previously authenticated, active User instance.
    User.objects.filter(pk=actor.pk).update(**change)
    assert actor.is_active and actor.access_status == "active"
    writes = {
        "save": lambda: services_website.save_content(target, actor=actor, data=data),
        "release": lambda: services_website.set_release(target, actor=actor, released=False, revision=page.revision),
        "delay": lambda: services_website.set_delay(target, "talk", actor=actor, minutes=10),
        "upload": lambda: upload_asset(target, actor=actor, file=file, alt_text="Photo"),
        "delete": lambda: delete_asset(target, asset.pk, actor=actor),
    }
    with pytest.raises(PermissionDenied):
        writes[operation]()
    page.refresh_from_db()
    assert page.revision == 1 and page.released
    assert EventPageAsset.objects.filter(pk=asset.pk).exists()
    assert page.sessions.get().delay_minutes == 0
    file.read.assert_not_called()
    assert not AuditLog.objects.filter(action__startswith="event.website_").exists()


@pytest.mark.parametrize("change", [{"is_active": False}, {"access_status": "suspended"}])
def test_atomic_publish_and_release_reject_stale_actor(change):
    _, actor, event, page, _ = website_fixture(released=False)
    event.status = "draft"
    event.save(update_fields=["status"])
    User.objects.filter(pk=actor.pk).update(**change)
    with pytest.raises(PermissionDenied):
        services.publish(event, actor=actor, publish_website=True, website_revision=page.revision)
    event.refresh_from_db()
    page.refresh_from_db()
    assert event.status == "draft" and not page.released
    assert not AuditLog.objects.filter(action__in=["event.published", "event.website_released"]).exists()


def test_refreshed_actor_reaches_subsequent_permission_checks_and_audit(monkeypatch):
    _, actor, event, page, _ = website_fixture()
    User.objects.filter(pk=actor.pk).update(display_name="Current account")
    real_can, real_audit = event_authority.can, services_website.audit
    checks, audits = [], []

    def check(current, target, permission):
        assert current is not actor and current.display_name == "Current account"
        checks.append(permission)
        return real_can(current, target, permission)

    def audit(current_page, current, action, **meta):
        assert current is not actor and current.display_name == "Current account"
        audits.append(action)
        return real_audit(current_page, current, action, **meta)

    monkeypatch.setattr(event_authority, "can", check)
    monkeypatch.setattr(services_website, "audit", audit)
    data = project(event)
    data["sections"][0]["title"] = "Updated speaker"
    services_website.save_content(event, actor=actor, data=data)
    assert {"view", "edit_details", "publish_schedule"} <= set(checks)
    assert audits == ["event.website_saved"]
    page.refresh_from_db()
    assert page.revision == 2
