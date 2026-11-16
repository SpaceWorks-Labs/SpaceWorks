"""Routes for personal access tokens and app connections (#196)."""
from urllib.parse import urlencode

from django.conf import settings
from django.http import HttpResponseRedirect
from django.urls import path
from django.views.decorators.csrf import csrf_exempt

from . import views_oauth, views_oauth_apps, views_tokens


def authorize_redirect(request):
    """The OAuth authorization endpoint: hand the browser to the console consent screen."""
    base = (settings.PUBLIC_APP_BASE_URL or "http://localhost:5000").rstrip("/")
    return HttpResponseRedirect(f"{base}/oauth/authorize?{urlencode(list(request.GET.lists()), doseq=True)}")


def _protocol_view(view_class):
    """django-oauth-toolkit's own protocol view, behind a per-client-address rate limit."""
    from .person_auth import _throttle

    view = view_class.as_view()

    def throttled(request, *args, **kwargs):
        from config.client_ip import get_throttle_client_ip
        from rest_framework.exceptions import Throttled
        from django.http import JsonResponse
        try:
            _throttle(f"oauth-protocol:{get_throttle_client_ip(request)}")
        except Throttled:
            return JsonResponse({"error": "slow_down"}, status=429, headers={"Retry-After": "60"})
        return view(request, *args, **kwargs)
    return csrf_exempt(throttled)


def protocol_urlpatterns():
    from oauth2_provider import views as dot
    patterns = [
        path("authorize/", authorize_redirect, name="authorize"),
        path("token/", _protocol_view(dot.TokenView), name="token"),
        path("revoke/", _protocol_view(dot.RevokeTokenView), name="revoke-token"),
        path("introspect/", _protocol_view(dot.IntrospectTokenView), name="introspect"),
    ]
    from oauth2_provider.settings import oauth2_settings
    if oauth2_settings.OIDC_ENABLED:
        patterns += [
            path(".well-known/openid-configuration", dot.ConnectDiscoveryInfoView.as_view(), name="oidc-connect-discovery-info"),
            path(".well-known/jwks.json", dot.JwksInfoView.as_view(), name="jwks-info"),
            path("userinfo/", _protocol_view(dot.UserInfoView), name="user-info"),
        ]
    return patterns


account_urlpatterns = [
    path("access-tokens", views_tokens.AccessTokenListCreateView.as_view(), name="auth-access-tokens"),
    path("access-tokens/<int:pk>", views_tokens.AccessTokenRevokeView.as_view(), name="auth-access-token-revoke"),
    path("access-token-scopes", views_tokens.PersonScopeCatalogView.as_view(), name="auth-access-token-scopes"),
    path("oauth/authorize", views_oauth.ConsentView.as_view(), name="auth-oauth-consent"),
    path("connected-apps", views_oauth.ConnectedAppListView.as_view(), name="auth-connected-apps"),
    path("connected-apps/<int:application_id>", views_oauth.ConnectedAppRevokeView.as_view(),
         name="auth-connected-app-revoke"),
]

staff_urlpatterns = [
    path("makerspace/<int:makerspace_id>/oauth-apps", views_oauth_apps.OAuthAppListCreateView.as_view(),
         name="admin-oauth-apps"),
    path("oauth-apps/<int:pk>", views_oauth_apps.OAuthAppDetailView.as_view(), name="admin-oauth-app"),
]
