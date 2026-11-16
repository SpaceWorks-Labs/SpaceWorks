"""Decision 223 (k), lane L3b: the attendee to guest to member funnel.

* `join_prefill` -- what the "Join" call to action pre-fills in the existing membership request
  (`POST member/makerspaces/{id}/admission`), from a registration the caller attended or a guest pass they
  hold. It is read-only; the request itself, vouching, forms and payment are the ordinary admission path.
* The converted link (`GuestPass.converted_membership`, status `converted`) is written by L1a's
  `guest_pass_lifecycle.mark_converted`, which membership activation already calls; nothing here writes it.
* `funnel_counts` -- attendees (first attendance in range, not yet a member), guests (of those, holders of a
  pass here), joined (of those, a membership activated on or after the first attendance). Distinct people,
  so the aggregate across spaces is not summable.
"""
from django.utils.translation import gettext
from apps.makerspaces.community_policy import CommunityError, funnel_on
from apps.makerspaces.models import GuestPass, MakerspaceMembership
from apps.makerspaces.platform import module_enabled


def _guest_pass_prefill(user, makerspace, pass_id):
    row = GuestPass.objects.select_related("holder").filter(pk=pass_id, makerspace=makerspace, holder=user).first()
    if row is None:
        return None
    return {"name": row.holder.display_name or row.holder.get_full_name() or row.holder.username,
            "email": row.holder.email, "phone": row.holder.phone, "source": "guest_pass",
            "source_ref": row.pk, "source_label": row.get_kind_display()}


def join_prefill(user, makerspace, *, registration_id=None, guest_pass_id=None):
    if not funnel_on(makerspace):
        raise CommunityError("join_funnel_off", gettext("The join call to action is not enabled here."), 404)
    if MakerspaceMembership.objects.filter(makerspace=makerspace, user=user, status="active").exists():
        raise CommunityError("already_member", gettext("You are already a member of this space."), 409)
    found = None
    if guest_pass_id:
        found = _guest_pass_prefill(user, makerspace, guest_pass_id)
    elif registration_id and module_enabled(makerspace, "events"):
        from apps.events.join_funnel_adapter import registration_prefill
        found = registration_prefill(user, makerspace, registration_id)
    if found is None:
        raise CommunityError("source_not_found", gettext("That event ticket or guest pass is not yours."), 404)
    return found


def funnel_counts(makerspace, start=None, end=None):
    """`{"attendees", "guests", "joined"}` for one space; zeros when events are off."""
    if not module_enabled(makerspace, "events"):
        return {"attendees": 0, "guests": 0, "joined": 0}
    from apps.events.join_funnel_adapter import first_attendances
    first = first_attendances(makerspace, start, end)
    activated = dict(MakerspaceMembership.objects.filter(
        makerspace=makerspace, user_id__in=list(first), activated_at__isnull=False,
    ).values_list("user_id", "activated_at"))
    attendees = {user for user, at in first.items() if user not in activated or activated[user] >= at}
    guests = set(GuestPass.objects.filter(makerspace=makerspace, holder_id__in=attendees)
                 .values_list("holder_id", flat=True))
    joined = {user for user in attendees if user in activated}
    return {"attendees": len(attendees), "guests": len(guests), "joined": len(joined)}
