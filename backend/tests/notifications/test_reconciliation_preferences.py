"""Conservative preference union retains negative policy without granting consent."""
import importlib
from types import SimpleNamespace

import pytest
from django.apps import apps

from apps.notifications.models_inbox import MemberNotificationPreference
from apps.notifications.models_preferences import NotificationPreference
from apps.notifications.preferences import personal_enabled
from tests.notifications.test_support_m1b import push_case  # noqa: F401

pytestmark = pytest.mark.django_db
conversion = importlib.import_module("apps.notifications.migrations._push_conversion_v1")


def test_conversion_intersects_existing_selection_and_preserves_email_opt_out(push_case):
    case = push_case
    saved = NotificationPreference.objects.get(makerspace=case.space, user=case.user)
    saved.channels, saved.email_fallback = ["native_push", "email", "in_app"], True
    saved.save()
    for channel in ("native_push", "email"):
        MemberNotificationPreference.objects.create(makerspace=case.space, user=case.user,
            feature="bookings", channel=channel, enabled=False)
    conversion.intersect_preferences(apps, "default")
    saved.refresh_from_db()
    assert saved.channels == ["in_app"] and not saved.email_fallback
    assert MemberNotificationPreference.objects.filter(enabled=False).count() == 2
    conversion.intersect_preferences(apps, "default")
    saved.refresh_from_db()
    assert saved.channels == ["in_app"] and not saved.email_fallback


def test_conversion_never_manufactures_new_selections_or_positive_consent(push_case):
    case = push_case
    NotificationPreference.objects.all().delete()
    MemberNotificationPreference.objects.create(makerspace=case.space, user=case.user,
        feature="bookings", channel="native_push", enabled=False)
    conversion.intersect_preferences(apps, "default")
    assert not NotificationPreference.objects.exists()
    assert not personal_enabled(case.space, case.user.pk, "bookings", "native_push")


def test_retained_physical_preferences_constrain_reads_without_optional_models(push_case, monkeypatch):
    case = push_case
    MemberNotificationPreference.objects.create(makerspace=case.space, user=case.user,
        feature="bookings", channel="native_push", enabled=False)
    original = apps.get_model

    def absent(label, model=None, *args, **kwargs):
        if label == "notifications":
            raise LookupError("optional app absent")
        return original(label, model, *args, **kwargs)

    monkeypatch.setattr(apps, "get_model", absent)
    assert not personal_enabled(case.space, case.user.pk, "bookings", "native_push")
    # Canonical omission also wins, independently of the old boolean opt-out.
    MemberNotificationPreference.objects.all().delete()
    NotificationPreference.objects.filter(user=case.user).update(channels=[])
    assert not personal_enabled(case.space, case.user.pk, "bookings", "native_push")


def test_malformed_selection_fails_closed_but_mandatory_email_keeps_its_exception(push_case):
    case = push_case
    NotificationPreference.objects.filter(user=case.user).update(channels={"native_push": True})
    assert not personal_enabled(case.space, case.user.pk, "bookings", "native_push")
    assert personal_enabled(case.space, case.user.pk, "hardware_requests", "email",
                            stream="hardware", event="closed_with_issue")
