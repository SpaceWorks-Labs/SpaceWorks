"""Live guest-pass holders for the desk's direct-loan borrower list (0.12.0, UI lane U1).

`_borrower_for_makerspace` already accepts a person holding a live guest pass; the list must offer
the same people or the desk cannot pick them. Rows mimic a membership for the serializer, with no
membership id, `is_guest_pass` set and the pass end in `pass_valid_until`.
"""
from types import SimpleNamespace

from apps.accounts.staff_identity import person_q
from apps.makerspaces.guest_pass_queries import active_pass_for
from apps.makerspaces.models import GuestPass


def guest_pass_rows(makerspace, *, exclude_user_ids=()):
    holders = (GuestPass.objects.filter(makerspace=makerspace, status__in=GuestPass.LIVE_STATUSES)
               .exclude(holder_id__in=list(exclude_user_ids)).select_related("holder")
               .order_by("holder__display_name", "holder_id"))
    seen, rows = set(), []
    for row in holders:
        user = row.holder
        if user.pk in seen or not person_q_matches(user):
            continue
        live = active_pass_for(user, makerspace)
        if live is None:
            continue
        seen.add(user.pk)
        rows.append(SimpleNamespace(id=None, user=user, is_guest_pass=True, pass_valid_until=live.valid_until))
    return rows


def person_q_matches(user):
    from apps.accounts.models import User
    return User.objects.filter(person_q(), pk=user.pk).exists()
