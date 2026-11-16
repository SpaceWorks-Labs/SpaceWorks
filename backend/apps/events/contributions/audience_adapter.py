"""Live posting audience checks shared by prefill and the C runtime adapter."""

from django.http import Http404
from django.utils import timezone

from apps.accounts.models import User
from apps.events.contributions.commands import active_member
from apps.events.contributions.models_roles import EventRolePosting
from apps.makerspaces.guards import require_feature, require_module
from apps.makerspaces.platform import module_enabled
from apps.makerspaces.servability import is_servable


def require_role_audience(*, actor_id, event_id, posting_id):
    actor = User.objects.filter(pk=actor_id).first()
    active_member(actor)
    posting = EventRolePosting.objects.select_related("event__makerspace").filter(pk=posting_id, event_id=event_id).first()
    if posting is None or not is_servable(posting.event.makerspace):
        raise Http404
    event = posting.event
    require_module(event.makerspace, "events")
    require_feature(event.makerspace, "events.volunteering" if posting.role == "volunteer" else "events.mentoring")
    if event.status != "published" or posting.state != "open" or not posting.opens_at <= timezone.now() < posting.closes_at:
        raise Http404
    if posting.visibility == "members":
        from apps.makerspaces.models import MakerspaceMembership
        if not module_enabled(event.makerspace, "membership") or not MakerspaceMembership.objects.filter(
                makerspace_id=event.makerspace_id, user_id=actor_id, status="active").exists():
            raise Http404
    elif posting.visibility == "audience_organizations":
        from apps.events.organization_audience import require_organization_audience
        if event.registration_audience != "participating_organizations":
            raise Http404
        require_organization_audience(event, actor)
    elif posting.visibility != "public":
        raise Http404
    return posting
