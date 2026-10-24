"""Owner certificate lookup covers registration and role subjects without identity guessing."""
from django.shortcuts import get_object_or_404
from rest_framework.exceptions import NotFound

from apps.events.models_certificates import EventAttendanceCertificate
from apps.events.participant_access import participant_space
from apps.makerspaces.models import MakerspaceMembership
from apps.presence.guard import MemberPresenceRequired, require_active_account

from .subjects import require_read


def owner_certificate(actor, makerspace_id, certificate_id):
    row = get_object_or_404(EventAttendanceCertificate.objects.select_related(
        "event__makerspace", "registration",
    ), pk=certificate_id, recipient_member_id=actor.pk)
    if row.registration_id:
        participant_space(actor, makerspace_id, row.registration_id)
    else:
        if row.event.makerspace_id != makerspace_id:
            raise NotFound()
        require_active_account(actor, row.event.makerspace)
        memberships = MakerspaceMembership.objects.filter(user=actor, makerspace_id=makerspace_id)
        if memberships.exists() and not memberships.filter(status="active").exists():
            raise MemberPresenceRequired()
    require_read(row, actor)
    return row
