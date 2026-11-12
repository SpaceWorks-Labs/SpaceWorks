"""Share/sitemap adapters for the global profile; only OPEN-WEB profiles are ever shared.

Resolve live consent BEFORE serving any cached card. Sitemap consumers must call the iterator on
each read, rather than caching an unfiltered publication list. A share card is logged-out
content, so it needs the open-web consent (`public_visible`) even though signed-in readers do not.
"""

from django.conf import settings
from drf_spectacular.utils import extend_schema, OpenApiResponse
from rest_framework.exceptions import NotFound
from rest_framework.response import Response

from apps.inventory.public_image_storage import public_url

from .account_profile import display_name_for_user
from .account_profile_access import resolve_by_handle
from .models_account_profile import AccountProfile
from .models_profiles import PublicHandle
from .public_profile_access import _request_tenant_ids
from .public_profile_cache import remember_share_card
from .public_profile_views import PublicProfileBase, ERRORS
from .website_serving import PublicCard, share_response


def profile_url(handle):
    origin = (settings.PUBLIC_APP_BASE_URL or "http://localhost:5000").rstrip("/")
    return f"{origin}/{handle}"


class PublicProfileShareView(PublicProfileBase):
    @extend_schema(tags=["Public profiles"], auth=[], responses={
        (200, "text/html"): OpenApiResponse(str, description="Live-gated OG/Twitter share metadata."),
        302: OpenApiResponse(description="Redirect to the current public handle."), **ERRORS,
    })
    def get(self, request, handle):
        from django.contrib.auth.models import AnonymousUser

        self.cache_headers()
        # A share card is read by crawlers: always the logged-out audience, whoever asks.
        profile, redirected = resolve_by_handle(handle, AnonymousUser(), request)
        from .account_profile_minors import is_minor_account
        if is_minor_account(profile.user):
            # H4: a minor's profile never gets a crawler card, guardian consent or not.
            raise NotFound()
        if redirected:
            return Response(status=302, headers={"Location": f"/share/profiles/{redirected}/"})
        current = PublicHandle.objects.get(user_id=profile.user_id)
        card = PublicCard(
            title=display_name_for_user(profile.user), description=profile.bio if profile.show_about else "",
            url=profile_url(current.handle), image_url=public_url(profile.avatar_key) or None,
            date="", location="", availability="", audience_label="Public maker profile",
            revision=f"{profile.updated_at.isoformat()}:{current.changed_at.isoformat()}",
        )
        response = share_response(card)
        remember_share_card(f"acct:{profile.user_id}", card)
        return response


def sitemap_profile_urls(request, *, spaces=None):
    from .account_profile_minors import is_minor_account
    from .account_profile_read import account_is_listable
    from .models import MakerspaceMembership

    try:
        scopes = _request_tenant_ids(request)
    except NotFound:
        # An unscoped host or origin publishes no profiles; it must not 404 the shared sitemap.
        return
    if len(set(scopes)) > 1:
        return
    profiles = AccountProfile.objects.filter(
        public_visible=True, public_consented_at__isnull=False, is_visible=True,
    ).select_related("user")
    members = MakerspaceMembership.all_tracks.filter(status="active")
    if scopes:
        members = members.filter(makerspace_id=scopes[0])
    elif spaces is not None:
        members = members.filter(makerspace__in=spaces)
    profiles = profiles.filter(user_id__in=members.values("user_id"))
    handles = dict(PublicHandle.objects.filter(user_id__in=profiles.values("user_id"))
                   .values_list("user_id", "handle"))
    for profile in profiles.iterator(chunk_size=200):
        if (profile.user_id in handles and account_is_listable(profile.user)
                and not is_minor_account(profile.user)):  # H4: minors are never indexed
            yield profile_url(handles[profile.user_id])
