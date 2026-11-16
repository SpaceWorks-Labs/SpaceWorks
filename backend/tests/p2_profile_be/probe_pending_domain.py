"""Not collected (no test_ prefix): probe why a pending tenant domain still serves."""
import pytest
from apps.makerspaces import public_profile_access as access
from apps.makerspaces.models import Makerspace
from .conftest import public_get

pytestmark = pytest.mark.django_db


def test_probe(published, other_space, monkeypatch):
    own = published.membership.makerspace
    own.frontend_domain = "own.example.test"; own.frontend_domain_status = "verified"; own.save()
    own.frontend_domain_status = "pending"; own.save(update_fields=["frontend_domain_status"])
    rows = list(Makerspace.objects.filter(frontend_domain__iexact="own.example.test").values("pk", "frontend_domain", "frontend_domain_status"))
    seen = []
    real = access._request_tenant_ids
    def spy(request):
        try:
            out = real(request); seen.append(("ok", request.get_host(), out)); return out
        except Exception as exc:
            seen.append(("raise", request.get_host(), type(exc).__name__)); raise
    monkeypatch.setattr(access, "_request_tenant_ids", spy)
    response = public_get("github", HTTP_HOST="own.example.test")
    with open("/workspace/backend/tests/.junit/probe.txt", "w") as fh:
        fh.write(f"rows={rows}\nseen={seen}\nstatus={response.status_code}\n")
