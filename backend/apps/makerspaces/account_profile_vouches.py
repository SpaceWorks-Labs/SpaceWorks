"""Vouches on the global profile (restored from the per-space model, decision 304).

A vouch is recorded per space by a member of that space. On the global profile it appears as
"vouched by <person> in <space>", under the same rules as the spaces section: only spaces the
person is an ACTIVE, directory-listed member of; only vouchers whose own profile is readable by
signed-in users (visible, listable account) and who have a handle to link to. Everyone else is
counted, never named: the number of people this person vouched for counts only readable profiles
too, so neither side can be inferred from a hidden profile. Gated by the `show_spaces` switch.

A named voucher must also (SECURITY-REVIEW L-P3) still be an active member of the space the vouch
was given in and show their own spaces section -- naming them says "member of <space>" -- and must
not be a minor, whose profile is never platform-wide (H4).
"""

from .account_profile_read import account_is_listable, display_name_for_user, handle_for
from .account_profile_spaces import listed_space_ids
from .models import MakerspaceMembership, MembershipVouch
from .models_account_profile import AccountProfile


def _readable(user, audience="member"):
    """Signed-in readers need a visible, listable account; the open web needs its public consent too."""
    from .account_profile_minors import is_minor_account

    profile = AccountProfile.objects.filter(user=user).first()
    if not (account_is_listable(user) and (profile is None or profile.is_visible)) or is_minor_account(user):
        return False
    return audience != "public" or bool(profile and profile.public_visible and profile.public_consented_at)


def _nameable(vouch, audience):
    voucher = vouch.voucher
    profile = AccountProfile.objects.filter(user=voucher).first()
    if profile is not None and not profile.show_spaces:
        return False
    if not MakerspaceMembership.all_tracks.filter(user=voucher, makerspace_id=vouch.makerspace_id,
                                                 status="active").exists():
        return False
    return _readable(voucher, audience)


def vouches_for(user, audience="member"):
    spaces = listed_space_ids(user)
    given = (MembershipVouch.objects.filter(makerspace_id__in=spaces, request__user=user)
             .select_related("voucher", "makerspace").order_by("makerspace__name", "pk"))
    named = []
    for vouch in given:
        voucher = vouch.voucher
        handle = handle_for(voucher)
        if handle and _nameable(vouch, audience):
            named.append({"handle": handle, "display_name": display_name_for_user(voucher),
                          "space_name": vouch.makerspace.name})
    received = (MembershipVouch.objects.filter(makerspace_id__in=spaces, voucher=user)
                .select_related("request__user"))
    count = len({v.request.user_id for v in received if _readable(v.request.user, audience)})
    return {"vouched_by": named, "vouched_count": count}
