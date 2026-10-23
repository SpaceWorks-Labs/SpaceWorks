from django.conf import settings

from apps.makerspaces.profile_services import display_name_for
from .models import EventMemberCard, EventMemberPresentation
from .policy import public_profile


def project_public(*, event_id, member_id, scope):
    row = EventMemberPresentation.objects.filter(event_id=event_id, member_id=member_id).first()
    selected = public_profile(row, scope) if row else None
    if not selected:
        return None
    profile, claim = selected
    card = EventMemberCard.objects.filter(presentation=row, scope=scope).first()
    if not card:
        return None
    origin = getattr(settings, "PUBLIC_APP_BASE_URL", "").rstrip("/")
    if not origin:
        return None
    return {"name": display_name_for(profile.membership), "skills": profile.skills[:20],
            "role": scope, "profile_url": f"{origin}/{claim.handle}",
            "photo_url": (f"/api/v1/public/event-programmes/{row.event.public_token}/member-cards/"
                          f"{card.public_id}/photo/" if profile.avatar_key else None)}
