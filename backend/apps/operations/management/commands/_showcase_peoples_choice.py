"""Tinkerspace People's choice (r2-peoples-choice, #181 S3; #134 walkthrough).

Turns the gallery and People's choice switches on and, through the real settings workflow, opens a
People's choice vote on the showcase hackathon for any signed-in member, closing in a week. No ballot
is invented: members vote live in the gallery, and staff publish the result in the walkthrough.
"""

from datetime import timedelta
from uuid import uuid4

from django.utils import timezone

from apps.makerspaces.models import Makerspace

FEATURES = ("events.project_gallery", "events.peoples_choice")


def seed_peoples_choice(space, manager, hackathon):
    from apps.events.judging.models_peoples_choice import PeoplesChoiceConfig
    from apps.events.judging.peoples_choice import update
    space.enabled_features = sorted(set(space.enabled_features or []) | set(FEATURES))
    Makerspace.objects.filter(pk=space.pk).update(enabled_features=space.enabled_features)
    current = PeoplesChoiceConfig.objects.filter(event=hackathon).values_list("version", flat=True).first() or 0
    update(hackathon.pk, actor=manager, data={"operation_id": uuid4(), "expected_version": current, "enabled": True,
                                              "audience": "members", "closes_at": timezone.now() + timedelta(days=7)})
