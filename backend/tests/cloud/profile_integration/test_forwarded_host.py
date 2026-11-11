"""Forwarded authority needs an independently authenticated exact ingress."""
from django.http import HttpResponse
from django.test import RequestFactory, override_settings
import pytest

from config.cloud_settings.forwarded_host import TrustedForwardedHostMiddleware


@pytest.mark.parametrize("change", [
    {"HTTP_X_SPACEWORKS_EDGE_SECRET":"forged"},
    {"REMOTE_ADDR":"192.0.2.1"},
    {"HTTP_HOST":"other.internal"},
    {"HTTP_X_FORWARDED_FOR":"198.51.100.1, 198.51.100.2"},
    {"HTTP_X_FORWARDED_HOST":"member.example, attacker.example"},
])
def test_untrusted_forwarding_never_reaches_application(change):
    reached=[]
    middleware=TrustedForwardedHostMiddleware(lambda request: reached.append(request) or HttpResponse("ok"))
    values=dict(REMOTE_ADDR="127.0.0.1", HTTP_HOST="api.internal", HTTP_X_FORWARDED_HOST="member.example",
                HTTP_X_FORWARDED_PROTO="https", HTTP_X_FORWARDED_FOR="198.51.100.1",
                HTTP_X_SPACEWORKS_EDGE_SECRET="a"*32)
    values.update(change)
    with override_settings(TRUST_FORWARDED_HOST=True, SPACEWORKS_DEPLOYMENT_PROFILE="full",
        TRUSTED_EDGE_CIDRS=["127.0.0.0/8"], TRUSTED_EDGE_UPSTREAM_HOSTS=["api.internal"],
        TRUSTED_EDGE_INGRESS_SECRET="a"*32, TRUSTED_PROXY_COUNT=1, USE_X_FORWARDED_HOST=True,
        ALLOWED_HOSTS=["api.internal","member.example"]):
        response=middleware(RequestFactory().post("/api/v1/something", **values))
    assert response.status_code == 400
    assert reached == []


def test_authenticated_forwarding_uses_external_authority():
    middleware=TrustedForwardedHostMiddleware(lambda request: HttpResponse(request.get_host()))
    with override_settings(TRUST_FORWARDED_HOST=True, SPACEWORKS_DEPLOYMENT_PROFILE="full",
        TRUSTED_EDGE_CIDRS=["127.0.0.0/8"], TRUSTED_EDGE_UPSTREAM_HOSTS=["api.internal"],
        TRUSTED_EDGE_INGRESS_SECRET="a"*32, TRUSTED_PROXY_COUNT=1, USE_X_FORWARDED_HOST=True,
        ALLOWED_HOSTS=["api.internal","member.example"]):
        request=RequestFactory().get("/api/v1/something", HTTP_HOST="api.internal",
            HTTP_X_FORWARDED_HOST="member.example", HTTP_X_FORWARDED_PROTO="https",
            HTTP_X_FORWARDED_FOR="198.51.100.1", HTTP_X_SPACEWORKS_EDGE_SECRET="a"*32)
        response=middleware(request)
    assert response.status_code == 200
    assert response.content == b"member.example"
