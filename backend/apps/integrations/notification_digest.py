"""Email-only batching; each constituent is re-authorized when the batch is sent."""
from django.utils.translation import gettext
import hashlib

from django.db import transaction
from django.utils import timezone

from apps.makerspaces.capability_eligibility import feature_enabled_servable_ids
from apps.makerspaces.platform import feature_enabled

from .models_contract import NotificationEnvelope


def constituents(summary):
    if not feature_enabled_servable_ids([summary.makerspace_id], "notifications.digests"):
        return []
    from .notification_resolution import eligible, target_eligible, selected_policy
    rows = NotificationEnvelope.objects.filter(pk__in=summary.context.get("envelope_ids", []),
        makerspace_id=summary.makerspace_id, recipient_id=summary.recipient_id,
        feature=summary.feature, timing_policy="digest")
    return [row for row in rows if eligible(row) and "email" in selected_policy(row)[0]
            and target_eligible(row, "email")]


def eligible_digest(summary):
    return bool(constituents(summary))


def render_digest(summary):
    from .notification_sources import render
    lines = []
    for row in constituents(summary):
        content = render(row)
        from .notification_links import external_links
        content = external_links(row.makerspace, content)
        lines.append(f"{content.get('subject', row.event)}\n{content.get('text', '')}")
    return {"subject": gettext("Your Space Works notification digest"), "text": "\n\n".join(lines)}


def collect_digest(envelope):
    from .notification_outbox import emit
    # Parent lock serializes a recipient/category batch across duplicate tasks.
    from apps.encryption.write_fence import assert_mapped_write_allowed
    with transaction.atomic():
        assert_mapped_write_allowed(envelope.makerspace_id)
        space = type(envelope.makerspace).objects.select_for_update().get(pk=envelope.makerspace_id)
        rows = list(NotificationEnvelope.objects.select_for_update().filter(
            makerspace_id=envelope.makerspace_id, recipient_id=envelope.recipient_id,
            feature=envelope.feature, timing_policy="digest", processed_at=None,
            available_at__lte=timezone.now()).order_by("pk")[:100])
        if not rows:
            return
        ids = [row.pk for row in rows]
        if feature_enabled(space, "notifications.digests"):
            key = hashlib.sha256(",".join(str(pk) for pk in ids).encode()).hexdigest()
            emit(makerspace=space, recipient=envelope.recipient,
                 feature=envelope.feature, stream=envelope.stream, event="daily_digest",
                 audience=envelope.audience, source_kind="notification.digest", source_id=key,
                 dedup_key=f"digest:{envelope.makerspace_id}:{key}", context={"envelope_ids": ids})
        # Keep disabled inputs for history and remove them from the due sweep.
        NotificationEnvelope.objects.filter(pk__in=ids).update(processed_at=timezone.now())
