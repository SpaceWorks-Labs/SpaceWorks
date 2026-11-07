"""Member certificate admission and holder lookup for registration and role subjects."""
from django.shortcuts import get_object_or_404
from rest_framework.exceptions import NotFound

from apps.events.models_certificates import EventAttendanceCertificate
from apps.events.participant_access import participant_space
from apps.makerspaces.models import MakerspaceMembership
from apps.presence.guard import MemberPresenceRequired, require_active_account

from .subjects import require_read


def require_member_space(actor, makerspace_id):
    from apps.events.judging.boundary import active_member
    from apps.makerspaces.models import Makerspace
    from apps.makerspaces.platform import module_enabled
    active_member(actor)
    space = Makerspace.objects.filter(pk=makerspace_id).first()
    if space is None or not module_enabled(space, "events"):
        raise NotFound()
    return space


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
