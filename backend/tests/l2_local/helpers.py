from datetime import timedelta
from uuid import uuid4

from django.utils import timezone

from apps.events.programme.broadcast_preview import create_composer, create_preview
from tests.events.lane_d_helpers import fixture


def on(space, *keys):
    space.enabled_features = sorted(set(space.enabled_features) | set(keys))
    space.save(update_fields=["enabled_features"])
    return space


def off(space, *keys):
    space.enabled_features = sorted(set(space.enabled_features) - set(keys))
    space.save(update_fields=["enabled_features"])
    return space


def composer(event, actor, design="classic"):
    return create_composer(event, actor, {"subject": "Hello", "body": "Welcome {{ name }}",
        "statuses": ["registered"], "attendance": "any", "render_schema_version": 2,
        "design": design, "ctas": []}, uuid4())


def command(**values):
    return {"operation_id": uuid4(), "expected_version": 1, **values}


def send_payload(preview, version=1):
    return command(expected_version=version, preview_id=preview["preview_id"], revision=preview["revision"],
                   recipient_count=preview["recipient_count"], confirm=True)


def previewed(monkeypatch, design="classic"):
    space, actor, member, event, registration = fixture(monkeypatch)
    campaign = composer(event, actor, design)
    preview = create_preview(campaign, actor, command())
    return space, actor, member, event, campaign, preview


def past(seconds=1):
    return timezone.now() - timedelta(seconds=seconds)
