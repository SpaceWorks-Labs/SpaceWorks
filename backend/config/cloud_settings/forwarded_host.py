"""Accept forwarded authority only on independently restricted edge ingress."""
import ipaddress
import hmac

from django.conf import settings
from django.http import JsonResponse


class TrustedForwardedHostMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        if not getattr(settings, "TRUST_FORWARDED_HOST", False):
            return self.get_response(request)
        if request.method in {"GET", "HEAD"} and request.path_info.rstrip("/") in {"/api/v1/health", "/api/v1/health/readiness"} and not request.META.get("HTTP_X_FORWARDED_HOST"):
            request.get_host()
            return self.get_response(request)
        if (settings.SPACEWORKS_DEPLOYMENT_PROFILE == "free" and request.method == "POST"
                and request.path_info == "/api/v1/internal/free/tick"
                and not request.META.get("HTTP_X_FORWARDED_HOST")):
            request.get_host()  # The tick still requires its own rate-limited secret.
            return self.get_response(request)
        try:
            peer = ipaddress.ip_address(request.META.get("REMOTE_ADDR", ""))
            networks = [ipaddress.ip_network(cidr) for cidr in settings.TRUSTED_EDGE_CIDRS]
            host = request.META.get("HTTP_HOST", "").lower()
            external = request.META.get("HTTP_X_FORWARDED_HOST", "")
            chain = request.META.get("HTTP_X_FORWARDED_FOR", "").split(",")
            supplied = request.META.get("HTTP_X_SPACEWORKS_EDGE_SECRET", "")
            if (not supplied.isascii() or not hmac.compare_digest(supplied, settings.TRUSTED_EDGE_INGRESS_SECRET)
                    or not any(peer in network for network in networks)
                    or host not in settings.TRUSTED_EDGE_UPSTREAM_HOSTS
                    or len(chain) != settings.TRUSTED_PROXY_COUNT
                    or not external or any(c in external for c in ",/\\\r\n@")
                    or request.META.get("HTTP_X_FORWARDED_PROTO") != "https"):
                raise ValueError()
            for address in chain:
                ipaddress.ip_address(address.strip())
            # Django independently checks the external authority against ALLOWED_HOSTS.
            request.get_host()
        except (ValueError, TypeError):
            return JsonResponse({"code": "untrusted_edge", "detail": "Trusted ingress required."}, status=400)
        return self.get_response(request)
