"""Control-panel step-up keeps its existing login/MFA gate and own session proof."""

from inspect import unwrap
from urllib.parse import urlencode

from django.contrib.auth.decorators import login_required
from django.shortcuts import redirect, render
from django.utils.http import url_has_allowed_host_and_scheme
from django.views.decorators.cache import never_cache
from django.views.decorators.csrf import csrf_protect
from rest_framework.exceptions import APIException

from apps.accounts.reauthentication import require_recent_reauth, verify
from apps.accounts.views_reauthentication import ReauthenticationThrottle


CONTROL_AUTHORITY_MODELS = frozenset({
    "accounts.user", "auth.group", "makerspaces.makerspacerole", "makerspaces.makerspacemembership",
    "events.eventstaffgrant", "events.eventstaffgrantinvite", "events.eventorganizer", "events.eventseriesorganizer",
    "bookings.bookingspacestaffgrant", "bookings.bookingspacestaffgrantinvite",
    "apiclients.apiclient", "apiclients.apikeyrequest", "organizations.organizationmembership",
    "organizations.organizationmakerspace",
})


def sensitive_control_request(request, callback):
    model_admin = getattr(callback, "model_admin", None)
    if model_admin is None:
        # UserAdmin's custom password URL retains the bound method through
        # admin_view's wrappers, but does not attach the model_admin attribute.
        model_admin = getattr(unwrap(callback), "__self__", None)
    model = getattr(model_admin, "model", None)
    label = model._meta.label_lower if model is not None else ""
    if label in CONTROL_AUTHORITY_MODELS:
        return True
    # A tenant edit can carry membership-role inline writes. Settings-only edits
    # retain their existing flow; any submitted role row requires step-up.
    return label == "makerspaces.makerspace" and any(
        key.endswith(("-role", "-assigned_role", "-DELETE")) for key in request.POST)


class RecentReauthenticationAdminMixin:
    def _recent_redirect(self, request):
        if request.method != "POST":
            return None
        try:
            require_recent_reauth(request)
        except APIException:
            return redirect("/mfa/reauth/?" + urlencode({"next": request.path}))
        return None

    def changeform_view(self, request, *args, **kwargs):
        result = self._recent_redirect(request)
        return result if result is not None else super().changeform_view(request, *args, **kwargs)

    def changelist_view(self, request, *args, **kwargs):
        result = self._recent_redirect(request)
        return result if result is not None else super().changelist_view(request, *args, **kwargs)

    def delete_view(self, request, *args, **kwargs):
        result = self._recent_redirect(request)
        return result if result is not None else super().delete_view(request, *args, **kwargs)


@login_required(login_url="/control/login/")
@csrf_protect
@never_cache
def control_reauthentication(request):
    from apps.accounts.control_mfa import session_verified
    if request.user.account_kind != "platform" or not request.user.is_superuser or not session_verified(request):
        return redirect("/mfa/control/")
    destination = request.GET.get("next", "/control/")
    if not url_has_allowed_host_and_scheme(destination, {request.get_host()}, require_https=request.is_secure()):
        destination = "/control/"
    data = {"next": destination}
    if request.method == "POST":
        if not ReauthenticationThrottle().allow_request(request, None):
            data["error"] = "Too many attempts. Try again later."
            return render(request, "accounts/control_reauthentication.html", data, status=429)
        try:
            verify(request, password=str(request.POST.get("password", ""))[:1024],
                   code=str(request.POST.get("code", ""))[:6])
            return redirect(destination)
        except APIException:
            data["error"] = "Identity verification failed. Use your current password and a new authenticator code."
    return render(request, "accounts/control_reauthentication.html", data)
