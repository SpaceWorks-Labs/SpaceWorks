"""Shortlist publication is checklist history, never an admission transition."""
from django.utils import timezone
from apps.events.hackathons.admission_models import HackathonConfig
from apps.payments.event_payouts.errors import require
from .milestone_models import EventStageMilestone
from .transactions import command
from .trigger_service import resolve_participant


def shortlist(*, event_id, actor, data):
    hackathon = HackathonConfig.objects.filter(event_id=event_id, enabled=True).exists()
    permission = "review_applications" if hackathon else "manage_registrations"
    owners = tuple(sorted(set(data["participant_ids"])))
    require(0 < len(owners) <= 100, "invalid_participant_selection", status=400)
    with command(event_id=event_id, actor=actor, data=data, action="stage.shortlist", permission=permission,
                 account_ids=owners) as ctx:
        if ctx.replay:
            return ctx.replay
        require(data["expected_version"] == ctx.event.version, "stale_version")
        ids = []
        for owner_id in owners:
            subject = resolve_participant(event=ctx.event, owner_id=owner_id)
            require(subject.application is not None or subject.registration is not None, "invalid_subject", status=404)
            marker = EventStageMilestone.objects.select_for_update().filter(event=ctx.event, member_id=owner_id,
                kind="shortlisted", withdrawn_at__isnull=True).first()
            if data["published"] and marker is None:
                marker = EventStageMilestone.objects.create(event=ctx.event, member_id=owner_id,
                    application=subject.application, registration=None if subject.application else subject.registration,
                    published_by=ctx.actor, published_at=timezone.now())
            elif not data["published"] and marker:
                marker.withdrawn_at, marker.version = timezone.now(), marker.version + 1
                marker.save(update_fields=["withdrawn_at", "version"])
            if marker:
                ids.append(marker.pk)
                ctx.audit("event.stage_form.shortlist_published" if data["published"] else "event.stage_form.shortlist_withdrawn",
                    marker, milestone_id=marker.pk, reason_code=data["reason_code"])
        ctx.event.version += 1
        ctx.event.save(update_fields=["version"])
        return ctx.finish(ctx.event, milestone_ids=ids)
