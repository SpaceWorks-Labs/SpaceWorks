"""Share/sitemap adapters for the always-on card (549), with live minor safeguards."""

from django.conf import settings
from drf_spectacular.utils import extend_schema, OpenApiResponse
from rest_framework.exceptions import NotFound
from rest_framework.response import Response

from .public_profile_card import public_card, resolve_card_handle
from .models_account_profile import AccountProfile
from .models_profiles import PublicHandle
from .public_profile_access import _request_tenant_ids
from .public_profile_cache import remember_share_card
from .public_profile_views import PublicProfileBase, ERRORS
from .website_serving import PublicCard, share_response


def profile_url(handle):
    origin = (settings.PUBLIC_APP_BASE_URL or "http://localhost:5000").rstrip("/")
    return f"{origin}/@{handle}"


class PublicProfileShareView(PublicProfileBase):
    @extend_schema(tags=["Public profiles"], auth=[], responses={
        (200, "text/html"): OpenApiResponse(str, description="Live-gated OG/Twitter share metadata."),
        302: OpenApiResponse(description="Redirect to the current public handle."), **ERRORS,
    })
    def get(self, request, handle):
        self.cache_headers()
        current, redirected = resolve_card_handle(handle, request)
        profile = AccountProfile.objects.filter(user_id=current.user_id).first()
        from .account_profile_minors import is_minor_account
        if is_minor_account(current.user):
            # Keep the separate H4 crawler/index safeguard; the JSON card is still available.
            raise NotFound()
        if redirected:
            return Response(status=302, headers={"Location": f"/share/profiles/{current.handle}/"})
        payload = public_card(current)
        card = PublicCard(
            title=payload["display_name"], description=payload.get("bio", ""),
            url=profile_url(current.handle), image_url=payload["avatar_url"],
            date="", location="", availability="", audience_label="Public maker profile",
            revision=f"{profile.updated_at.isoformat() if profile else ''}:{current.changed_at.isoformat()}",
        )
        response = share_response(card)
        remember_share_card(f"acct:{current.user_id}", card)
        return response


def sitemap_profile_urls(request, *, spaces=None):
    from .account_profile_minors import is_minor_account
    from .account_profile_read import account_is_listable
    from .models import MakerspaceMembership
    from .account_profile_spaces import listed_memberships, _public_space

    try:
        scopes = _request_tenant_ids(request)
    except NotFound:
        # An unscoped host or origin publishes no profiles; it must not 404 the shared sitemap.
        return
    if len(set(scopes)) > 1:
        return
    profiles = AccountProfile.objects.select_related("user")
    members = MakerspaceMembership.all_tracks.filter(status="active")
    if scopes:
        members = members.filter(makerspace_id=scopes[0])
    elif spaces is not None:
        members = members.filter(makerspace__in=spaces)
    profiles = profiles.filter(user_id__in=members.values("user_id"))
    handles = dict(PublicHandle.objects.filter(user_id__in=profiles.values("user_id"))
                   .values_list("user_id", "handle"))
    allowed_ids = set(scopes) if scopes else ({space.pk for space in spaces} if spaces is not None else None)
    for profile in profiles.iterator(chunk_size=200):
        # Use the card's live public membership rules on tenant Hosts AND Origins.
        eligible_ids = {m.makerspace_id for m in listed_memberships(profile.user) if _public_space(m.makerspace)}
        if not eligible_ids or (allowed_ids is not None and not eligible_ids.intersection(allowed_ids)):
            continue
        if (profile.user_id in handles and account_is_listable(profile.user)
                and not is_minor_account(profile.user)):  # H4: minors are never indexed
            yield profile_url(handles[profile.user_id])
