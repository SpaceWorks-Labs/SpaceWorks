"""Distinct opt-in device alerts, recipient authority and credential-free templates."""

from datetime import timedelta

import pytest
from django.core.exceptions import ValidationError
from django.utils import timezone

from apps.devices.models import Device
from apps.devices.notifications import notify_device_state
from apps.devices.services_offline import scan_offline_devices
from apps.integrations.chat_templates import chat_entry, validate_chat_template_string
from apps.integrations.email_templates_registry import get_entry, validate_email_template_strings
from apps.integrations.models import NotificationChannel, NotificationFeature, NotificationPreference
from apps.integrations.models_recipients import NotificationRecipient
from apps.integrations.notification_catalog import DEFAULT_CHANNEL_STATE, FEATURE_EVENTS, is_notification_enabled
from apps.integrations.recipients_selection import FEATURE_MODULES, SELECTABLE_FEATURES
from apps.integrations.staff_notifications import staff_emails_for_feature, staff_user_ids_for_feature
from apps.makerspaces.models import MakerspaceMembership
from tests.devices.helpers import active_device, device_space, staff_client
from tests.return_helpers import make_member

pytestmark = pytest.mark.django_db


def test_devices_catalog_keeps_external_channels_off_and_personal_inbox_on():
    space = device_space("device-alert-defaults")
    assert NotificationFeature.DEVICES in SELECTABLE_FEATURES
    assert FEATURE_MODULES[NotificationFeature.DEVICES] == "devices"
    assert FEATURE_EVENTS[NotificationFeature.DEVICES][:2] == ("offline", "recovered")
    assert set(FEATURE_EVENTS[NotificationFeature.DEVICES][2:]) == {
        "adapter_attention", "adapter_runout", "adapter_session_ending", "adapter_access_denied",
        "adapter_detection", "adapter_job_review"}
    assert set(DEFAULT_CHANNEL_STATE[NotificationFeature.DEVICES]) == set(NotificationChannel.values)
    assert is_notification_enabled(space, "devices", NotificationChannel.IN_APP)
    assert not any(is_notification_enabled(space, "devices", channel)
                   for channel in NotificationChannel.values if channel != NotificationChannel.IN_APP)
    NotificationPreference.objects.create(makerspace=space, feature="devices", channel="email", enabled=True)
    assert is_notification_enabled(space, "devices", "email")
    assert not is_notification_enabled(space, "devices", "telegram")


def test_device_fallback_is_active_manage_devices_staff_in_this_tenant():
    first, second = device_space("device-alert-first"), device_space("device-alert-second")
    manager, _client = staff_client(first, "device-alert-manager")
    staff_client(second, "device-alert-foreign")
    make_member("device-alert-inventory", first, membership_role=MakerspaceMembership.Role.INVENTORY_MANAGER)
    inactive = make_member("device-alert-inactive", first)
    # make_member holds a staff-track row (one account per person), which the default manager does not see.
    MakerspaceMembership.staff_tracks.filter(makerspace=first, user=inactive).update(status="revoked")
    assert staff_emails_for_feature(first, "devices", event="offline") == [manager.email]
    assert staff_user_ids_for_feature(first, "devices", event="offline") == [manager.pk]


def test_explicit_user_selection_matches_email_and_push_and_honors_opt_out():
    space = device_space("device-alert-selected")
    staff_client(space, "device-alert-selected-manager")
    member = make_member("device-alert-selected-member", space, membership_role=MakerspaceMembership.Role.CUSTOM)
    NotificationRecipient.objects.create(makerspace=space, feature="devices", event="offline", kind="user", user=member)
    assert staff_emails_for_feature(space, "devices", event="offline") == [member.email]
    assert staff_user_ids_for_feature(space, "devices", event="offline") == [member.pk]
    MakerspaceMembership.objects.filter(makerspace=space, user=member).update(receives_notifications=False)
    assert staff_emails_for_feature(space, "devices", event="offline") == []
    assert staff_user_ids_for_feature(space, "devices", event="offline") == []


def test_templates_are_staff_only_validated_and_contain_no_secrets():
    for event in ("offline", "recovered"):
        entry = get_entry("devices", "staff", event)
        assert entry is chat_entry("devices", event)
        assert get_entry("devices", "requester", event) is None
        assert {field["name"] for field in entry.fields} == {
            "device.id", "device.name", "device.kind", "device.state", "device.last_seen_at", "device.offline_since", "now",
        }
        validate_email_template_strings("devices", "staff", event, entry.default_subject, entry.default_text, "")
        validate_chat_template_string("devices", event, "{{ device.name }} {{ device.state }}")
    with pytest.raises(ValidationError):
        validate_chat_template_string("devices", "offline", "{% invalid %}")


def test_notifications_are_on_commit_and_capture_the_state_edge(monkeypatch, django_capture_on_commit_callbacks):
    import json
    from apps.devices.services_events import record_device_event
    from apps.devices.models import DeviceEvent
    from apps.integrations.models_contract import NotificationEnvelope
    from apps.integrations.notification_tasks import deliver_envelope
    space, manager, _client, device_id, _private = active_device("device-alert-edge")
    row = Device.objects.get(pk=device_id)
    observed = []
    monkeypatch.setattr("apps.integrations.notification_outbox.enqueue", observed.append)
    row.offline_since = timezone.now()
    row.save(update_fields=["offline_since"])
    with django_capture_on_commit_callbacks(execute=True):
        edge = record_device_event(space, row, DeviceEvent.EventType.OFFLINE)
        notify_device_state(space, row, "offline", now=timezone.now())
        envelope = NotificationEnvelope.objects.get(event="offline", recipient=manager)
        assert not observed
        row.offline_since = None
    assert observed == [envelope.pk]
    assert envelope.audience == "staff" and envelope.source_kind == "devices.state_edge"
    assert envelope.source_id == str(edge.pk) and edge.device_id == row.pk
    rendered = json.loads(envelope.message_body)
    assert "offline" in rendered["text"].lower()
    assert envelope.context == {"device.id": str(row.pk)}
    # The historical edge, not these template scalars, remains the source authority.
    assert str(_private) not in envelope.message_body
    deliver_envelope.run(envelope.pk)
    envelope.refresh_from_db()
    assert envelope.processed_at is not None


def test_default_off_emits_no_external_delivery(monkeypatch, django_capture_on_commit_callbacks):
    space, _manager, _client, device_id, _key = active_device("device-alert-off")
    Device.objects.filter(pk=device_id).update(last_seen_at=timezone.now()-timedelta(hours=1))
    calls = []
    monkeypatch.setattr("apps.integrations.notify.dispatch_email", lambda **kw: calls.append(kw))
    monkeypatch.setattr("apps.integrations.notify.dispatch_channel", lambda **kw: calls.append(kw))
    with django_capture_on_commit_callbacks(execute=True):
        scan_offline_devices()
    assert calls == []


def test_provider_exception_does_not_fail_offline_scan_or_recovery(monkeypatch, django_capture_on_commit_callbacks):
    from tests.devices.helpers import heartbeat, signed_headers
    _space, _manager, _client, device_id, private = active_device("device-alert-failure")
    Device.objects.filter(pk=device_id).update(last_seen_at=timezone.now()-timedelta(hours=1))
    def fail(**_kwargs):
        raise RuntimeError("provider unavailable")
    monkeypatch.setattr("apps.integrations.notify.dispatch_channel", fail)
    space = Device.objects.get(pk=device_id).makerspace
    NotificationPreference.objects.create(makerspace=space, feature="devices", channel="telegram", enabled=True)
    with django_capture_on_commit_callbacks(execute=True):
        assert scan_offline_devices()["offline"] == 1
        assert heartbeat(signed_headers(device_id, 1, private)).status_code == 200
    assert Device.objects.get(pk=device_id).offline_since is None


def test_device_stream_visible_to_identity_manager_and_hidden_without_module():
    from apps.admin_api.views_email_templates_common import _visible_streams
    from tests.module_helpers import disable_module
    space = device_space("device-alert-template-gate")
    manager, _client = staff_client(space, "device-alert-template-manager")
    assert "devices" in _visible_streams(manager, space.pk)
    disable_module(space, "devices")
    assert "devices" not in _visible_streams(manager, space.pk)


def test_choice_migrations_match_runtime_fields():
    from django.apps import apps
    from django.db.migrations.loader import MigrationLoader
    # Historical migrations intentionally freeze old enums. Compare the final
    # state, including later choices-only migrations such as integrations/0037.
    loader = MigrationLoader(None)
    state = loader.project_state(loader.graph.leaf_nodes()).apps
    checked = set()
    for app_label in ("integrations", "devices"):
        for model in apps.get_app_config(app_label).get_models():
            migrated = state.get_model(app_label, model._meta.model_name)
            for runtime in model._meta.local_fields:
                field = migrated._meta.get_field(runtime.name)
                if runtime.choices is not None or field.choices is not None:
                    assert list(field.choices or []) == list(runtime.choices or []), (model._meta.label, runtime.name)
                    assert field.max_length == runtime.max_length
                    checked.add((model._meta.label, runtime.name))
    assert {("integrations.ChatTemplate", "feature"), ("devices.DeviceEvent", "event_type")} <= checked


def test_device_delivery_is_suppressed_if_module_is_disabled_before_commit(monkeypatch, django_capture_on_commit_callbacks):
    from tests.module_helpers import disable_module
    space, _manager, _client, device_id, _key = active_device("device-alert-disable")
    calls = []
    monkeypatch.setattr("apps.integrations.notify.dispatch_channel", lambda **kw: calls.append(kw))
    NotificationPreference.objects.create(makerspace=space, feature="devices", channel="telegram", enabled=True)
    with django_capture_on_commit_callbacks(execute=True):
        notify_device_state(space, Device.objects.get(pk=device_id), "offline", now=timezone.now())
        disable_module(space, "devices")
    assert calls == []


def test_foreign_named_recipient_cannot_receive_device_notification():
    local, foreign = device_space("device-alert-local"), device_space("device-alert-outsider")
    outsider = make_member("device-alert-outsider-user", foreign)
    NotificationRecipient.objects.create(makerspace=local, feature="devices", event="offline", kind="user", user=outsider)
    assert staff_emails_for_feature(local, "devices", event="offline") == []
    assert staff_user_ids_for_feature(local, "devices", event="offline") == []


def test_device_template_direct_access_with_module_off_is_400():
    from apps.makerspaces.guards import SurfaceOff
    from apps.admin_api.views_email_templates_common import _resolve_makerspace
    from tests.module_helpers import disable_module
    space = device_space("device-alert-template-off")
    manager, _client = staff_client(space, "device-alert-template-off-manager")
    disable_module(space, "devices")
    with pytest.raises(SurfaceOff) as error:
        _resolve_makerspace(manager, space.pk, "devices")
    assert error.value.status_code == 404 and error.value.key == "devices"
