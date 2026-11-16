"""Who may read an account profile. Every refusal is the SAME 404 (decision 303).

* Signed-in viewers read any visible profile anywhere, with no consent needed (303a).
* Logged-out viewers additionally need the open-web consent (`public_visible` + a consent stamp,
  303b), a live handle (they can only arrive through one) and, on a verified tenant domain, the
  person must be an active member of that tenant -- a space's own domain never shows strangers.
* A hidden profile, a restricted/suspended/inactive account and a non-existent one are
  indistinguishable (303c).
* A minor (H4, decision 336a) is never platform-wide: signed-in readers must share an active space
  with them, and the open web also needs a current guardian consent (`account_profile_minors`).
"""

from django.utils import timezone
from rest_framework.exceptions import NotFound

from .account_profile_read import account_is_listable
from .account_profile_spaces import listed_space_ids
from .models_account_profile import AccountProfile
from .models_profiles import PublicHandle, PublicHandleRedirect
from .public_profile_access import _request_tenant_ids


def can_read(profile, viewer, request=None):
    if profile is None or not account_is_listable(profile.user) or not profile.is_visible:
        return False
    from .account_profile_minors import guardian_consented, is_minor_account, shares_space

    minor = is_minor_account(profile.user)
    if viewer is not None and getattr(viewer, "is_authenticated", False) and viewer.is_active:
        return not minor or viewer.pk == profile.user_id or shares_space(profile.user, viewer)
    if not (profile.public_visible and profile.public_consented_at):
        return False
    if minor and not guardian_consented(profile.user):
        return False
    if not PublicHandle.objects.filter(user_id=profile.user_id).exists():
        return False
    if request is not None:
        scopes = _request_tenant_ids(request)
        if scopes and not set(scopes) <= listed_space_ids(profile.user):
            return False
    return True


def resolve_by_handle(handle, viewer, request=None):
    """`(profile, redirected_to_handle_or_None)`; raises the one 404 otherwise."""
    claim = PublicHandle.objects.filter(handle__iexact=handle, user__isnull=False).select_related("user").first()
    redirected = None
    if claim is None:
        retired = PublicHandleRedirect.objects.filter(
            handle__iexact=handle, expires_at__gt=timezone.now(), user__isnull=False).first()
        claim = PublicHandle.objects.filter(user_id=retired.user_id).select_related("user").first() if retired else None
        redirected = claim.handle if claim else None
    profile = AccountProfile.objects.filter(user_id=claim.user_id).select_related("user").first() if claim else None
    # A retired URL redirects only while the target is itself readable by this viewer.
    if not can_read(profile, viewer, request):
        raise NotFound()
    return profile, redirected


def resolve_by_account(user_id, viewer, request=None):
    """Account-id links serve signed-in viewers only (a member with no handle has no public URL)."""
    if viewer is None or not getattr(viewer, "is_authenticated", False):
        raise NotFound()
    profile = AccountProfile.objects.filter(user_id=user_id).select_related("user").first()
    if not can_read(profile, viewer, request):
        raise NotFound()
    return profile
