"""The "Here now" projection (decision 307b): who is checked in, as person cards, per audience.

One function answers for the public page, the signed-in page and a paired display. A person is shown as
a card only when ALL hold: the space shows names, they did not hide their presence, they are a member
(not a guest, not a minor here) and their global profile is readable by this audience (303: any
signed-in user reads a visible profile; a logged-out visitor needs the open-web consent). Everyone else
is only counted, so the total never changes with the audience, only how much of it is named.

PROFILE-2's `account_profile_access.can_read` is the single readability rule; `_card` is the one
place that maps a profile onto a card (decision 304: the card holds identity plus the two section
toggles it uses, status and skills).
"""
from apps.makerspaces.account_profile_access import can_read
from apps.makerspaces.community_policy import minors_on, policy_for
from apps.makerspaces.minors import is_minor
from apps.makerspaces.models import MinorProfile
from apps.makerspaces.models_account_profile import AccountProfile
from apps.makerspaces.models_profiles import PublicHandle
from apps.inventory.public_image_storage import public_url

from .display import present_rows
from .privacy import settings_for

MAX_CARDS = 24
MAX_SKILLS = 4


def _minor_ids(space, user_ids):
    if not minors_on(space):
        return set()
    policy = policy_for(space)
    rows = MinorProfile.objects.filter(makerspace=space, user_id__in=user_ids)
    return {row.user_id for row in rows if is_minor(row, policy)}


def _card(profile, handle, row):
    card = {
        "handle": handle,
        "display_name": profile.user.display_name or profile.user.get_full_name().strip() or profile.user.username,
        "avatar_url": public_url(profile.avatar_key) or None,
        "headline": profile.headline,
        "status": ({"preset": profile.status, "note": profile.status_note}
                   if profile.show_status and (profile.status or profile.status_note) else None),
        "skills": ([s.get("name") for s in (profile.skills or []) if isinstance(s, dict) and s.get("name")][:MAX_SKILLS]
                   if profile.show_skills else []),
        "presence_status": row.status,
        "since": row.started_at.isoformat(),
    }
    return card


def here_now(space, viewer=None, request=None):
    policy = settings_for(space)
    rows = [r for r in present_rows(space) if not (r.membership_id and r.membership.status != "active")]
    candidates = [r for r in rows if policy.show_names and r.membership_id and r.status != "guest"
                  and not r.hide_on_display]
    ids = [r.account_id for r in candidates]
    minors = _minor_ids(space, ids)
    profiles = {p.user_id: p for p in AccountProfile.objects.filter(user_id__in=ids).select_related("user")}
    handles = dict(PublicHandle.objects.filter(user_id__in=ids).values_list("user_id", "handle"))
    people = []
    for row in candidates:
        profile = profiles.get(row.account_id)
        if row.account_id in minors or profile is None or not can_read(profile, viewer, request):
            continue
        if len(people) < MAX_CARDS:
            people.append(_card(profile, handles.get(row.account_id), row))
    signed_in = bool(viewer is not None and getattr(viewer, "is_authenticated", False))
    return {"audience": "member" if signed_in else "public", "people": people,
            "others_count": len(rows) - len(people), "total": len(rows)}
