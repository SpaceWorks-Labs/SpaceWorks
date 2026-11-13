"""#183B gap 14: a notification whose source module or capability is off is never emitted or delivered."""

import ast
import pathlib
import re

import pytest
from django.db import transaction

from apps.integrations import notification_catalog_sources as sources
from apps.integrations.notification_catalog import FEATURE_EVENTS
from apps.integrations.recipients_selection import FEATURE_MODULES
from apps.makerspaces.capabilities import FEATURES
from apps.makerspaces.module_registry import MODULE_KEYS
from apps.operations.report_sources import known_source
from tests.module_helpers import disable_module
from tests.return_helpers import make_space

APPS = pathlib.Path(__file__).resolve().parents[2] / "apps"


def _known(source):
    return source is None or known_source(source)


def test_every_catalogue_family_has_a_source_or_is_platform_level():
    # API_ACCESS is the platform family: no single space switch owns it.
    platform_families = {"api_access"}
    for feature in FEATURE_EVENTS:
        assert feature in FEATURE_MODULES or feature in platform_families, feature
        assert _known(FEATURE_MODULES.get(feature)), feature


def test_every_event_override_names_a_catalogue_event_and_a_real_switch():
    for (feature, event), source in sources.EVENT_SOURCES.items():
        assert event in FEATURE_EVENTS.get(feature, ()), (feature, event)
        assert known_source(source), (feature, event, source)
        for part in source.split("|"):
            assert part in (FEATURES if "." in part else MODULE_KEYS), part


def test_every_catalogue_event_resolves_to_a_known_source():
    for feature, events in FEATURE_EVENTS.items():
        for event in events:
            assert _known(sources.event_source(feature, event)), (feature, event)
            assert _known(sources.family_source(feature)), feature


def test_every_emit_call_site_event_is_mapped_or_exempt():
    """A new `emit_notification(..., event="x.y")` must declare its source here."""
    unmapped = []
    for path in APPS.rglob("*.py"):
        if "migrations" in path.parts or "management" in path.parts:
            continue
        tree = ast.parse(path.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if not (isinstance(node, ast.Call) and getattr(node.func, "id", "") == "emit_notification"):
                continue
            event = next((kw.value for kw in node.keywords if kw.arg == "event"), None)
            if isinstance(event, ast.Constant):
                value = event.value
            elif isinstance(event, ast.JoinedStr) and event.values and isinstance(event.values[0], ast.Constant):
                value = event.values[0].value
            else:
                continue  # dynamic: the reminder sweep, gated by its ReminderSource
            if value not in sources.EMIT_EXEMPT and sources.emit_source(value) is None:
                unmapped.append(f"{path.relative_to(APPS)}: {value}")
    assert not unmapped, unmapped
    for source in sources.EMIT_SOURCES.values():
        assert source in MODULE_KEYS, source


@pytest.mark.django_db
def test_event_live_is_false_only_while_its_capability_is_off():
    space = make_space("notif-source-shop")
    space.enabled_modules = sorted(set(space.enabled_modules) | {"shop"})
    space.save(update_fields=["enabled_modules"])
    assert sources.event_live(space, "payments", "shop_order_paid") is True
    disable_module(space, "shop")
    space.refresh_from_db()
    assert sources.event_live(space, "payments", "shop_order_paid") is False
    # The core ledger events keep flowing.
    assert sources.event_live(space, "payments", "payment_received") is True
    # Unknown events keep their caller's own gate.
    assert sources.event_live(space, "payments", "not_in_catalogue") is True


@pytest.mark.django_db
def test_feature_available_narrows_by_event():
    from apps.integrations.recipients import feature_available

    space = make_space("notif-source-feature-available")
    space.enabled_features = [key for key in space.enabled_features if key != "finance.donations"]
    space.save(update_fields=["enabled_features"])
    assert feature_available(space, "payments") is True
    assert feature_available(space, "payments", event="donation_received") is False


@pytest.mark.django_db(transaction=True)
def test_emit_notification_writes_nothing_while_the_source_module_is_off():
    from apps.notifications.emit import emit_notification
    from apps.notifications.models import Notification

    space = make_space("notif-source-emit")
    space.enabled_modules = sorted(set(space.enabled_modules) | {"notifications", "stocktake"})
    space.save(update_fields=["enabled_modules"])
    with transaction.atomic():
        emit_notification(space, title="Stocktake ready", event="stocktake.completed")
    assert Notification.objects.filter(makerspace=space, event="stocktake.completed").count() == 1

    disable_module(space, "stocktake")
    space.refresh_from_db()
    with transaction.atomic():
        emit_notification(space, title="Stocktake ready", event="stocktake.completed")
    assert Notification.objects.filter(makerspace=space, event="stocktake.completed").count() == 1


@pytest.mark.django_db
def test_dispatch_channel_records_a_skip_for_an_off_source():
    from apps.integrations.dispatch_channels import dispatch_channel

    space = make_space("notif-source-room")
    space.enabled_modules = sorted(set(space.enabled_modules) | {"slack"})
    space.save(update_fields=["enabled_modules"])
    space.enabled_features = [key for key in space.enabled_features if key != "finance.sponsors"]
    space.save(update_fields=["enabled_features"])
    rows = dispatch_channel(makerspace=space, channel="slack", feature="payments", event="perk_due",
                            text_body="Perk due")
    assert len(rows) == 1
    assert rows[0].status == "skipped"
    assert rows[0].error in {"notification_source_disabled", "notification_channel_configuration_disabled",
                             "notification_channel_module_disabled"}


@pytest.mark.django_db
def test_email_blocked_reason_names_the_off_source():
    from apps.integrations.email_preferences import blocked_reason

    space = make_space("notif-source-email")
    space.enabled_features = [key for key in space.enabled_features if key != "membership.broadcasts"]
    space.save(update_fields=["enabled_features"])
    assert blocked_reason(space, "member@example.test", feature="members", event="broadcast") == \
        "notification_source_disabled"
    assert blocked_reason(space, "member@example.test", feature="members", event="approved") == ""


def test_sources_module_documents_every_override_family():
    text = (APPS / "integrations" / "notification_catalog_sources.py").read_text(encoding="utf-8")
    assert re.search(r"#183B", text)
