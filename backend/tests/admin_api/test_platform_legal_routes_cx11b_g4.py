"""Core platform legal methods are global browser-only authority, with exact persisted effects."""
import pytest
from django.urls import reverse

from apps.accounts.models import User
from apps.integrations.models_legal import PlatformLegalPage
from apps.operations.legal_pages import set_platform_page
from tests.modules.switch_matrix_object_helpers import client_for, object_world
from tests.operations.route_support_cx11b_g4 import cycle, send
from tests.return_helpers import make_user

pytestmark = [pytest.mark.django_db, pytest.mark.area_platform, pytest.mark.area_frontend_shell]


@pytest.mark.parametrize("method", ["GET", "PUT", "DELETE"])
@pytest.mark.parametrize("native_outsider", [False, True], ids=["browser-outsider", "native-outsider"])
def test_platform_legal_methods_require_platform_authority_and_change_exact_text(method, native_outsider):
    space, _client, _ = object_world(False)
    root = make_user("g4-platform-legal", role=User.Role.SUPERADMIN, access_status="active")
    client = client_for(root, space, False)
    actor = User.objects.get(username="sx-real-object-manager")
    foreign = client_for(actor, space, native_outsider)
    row = set_platform_page("terms", "", "# Retained global terms")
    url = reverse("admin-platform-legal-page", kwargs={"slug": "terms"})
    body = {"markdown": "# Changed global terms", "language": ""} if method == "PUT" else {}

    def check(response):
        if method == "DELETE":
            assert not PlatformLegalPage.objects.filter(pk=row.pk).exists()
        else:
            row.refresh_from_db()
            text = "# Changed global terms" if method == "PUT" else "# Retained global terms"
            assert (row.markdown, response.data["markdown"], response.data["source"]) == (text, text, "platform")
    # No tenant switch governs the operator's legal text. Platform device grants are
    # forbidden; an ordinary staff native/browser caller retains 403 (494).
    cycle(space, None, lambda: send(client, method, url, body), check,
          on=(204 if method == "DELETE" else 200, None),
          audit=("platform.legal_page_updated",) if method != "GET" else (),
          foreign=lambda: send(foreign, method, url, body), foreign_pair=(403, "permission_denied"))
