"""#190 follow-up: a Space Manager edits their own space's chat templates. Local only."""

from types import SimpleNamespace

import pytest
from django.core.cache import cache

from apps.audit.models import AuditLog
from apps.integrations.models_chat_templates import ChatTemplate
from tests.r2_superadmin_local.helpers import api, manager, member, space, superadmin

pytestmark = pytest.mark.django_db
BODY = {"feature": "certifications", "event": "expiring", "text_body": "Training at {{ makerspace.name }}", "is_active": True}


def url(lab, pk=None):
    return f"/api/v1/admin/makerspace/{lab.pk}/chat-templates" + (f"/{pk}" if pk else "")


@pytest.fixture
def world():
    cache.clear()
    lab, other = space("chat-lab"), space("chat-other")
    return SimpleNamespace(lab=lab, other=other, boss=manager(lab), other_boss=manager(other), person=member(lab))


def test_a_space_manager_adds_changes_and_removes_their_own_templates(world):
    client = api(world.boss)
    created = client.post(url(world.lab), BODY, format="json")
    assert created.status_code == 201, created.json()
    pk = created.json()["id"]
    assert client.get(url(world.lab)).json()["results"][0]["id"] == pk
    assert client.patch(url(world.lab, pk), {"is_active": False}, format="json").json()["is_active"] is False
    assert client.delete(url(world.lab, pk)).status_code == 204
    saved = AuditLog.objects.filter(action="chat_template.saved", makerspace=world.lab, actor=world.boss)
    assert saved.count() == 2 and AuditLog.objects.filter(action="chat_template.deleted", actor=world.boss).exists()


def test_another_spaces_manager_and_members_are_refused(world):
    row = ChatTemplate.objects.create(makerspace=world.lab, feature="certifications", event="expiring", text_body="x")
    assert api(world.other_boss).get(url(world.lab)).status_code in {403, 404}
    assert api(world.other_boss).delete(url(world.lab, row.pk)).status_code in {403, 404}
    # A manager of their own space cannot reach another space's row through their own space's path.
    assert api(world.other_boss).delete(url(world.other, row.pk)).status_code == 404
    assert api(world.person).get(url(world.lab)).status_code in {401, 403, 404}
    assert ChatTemplate.objects.filter(pk=row.pk).exists()


def test_the_superadmin_path_is_unchanged(world):
    root = superadmin("chat-root")
    response = api(root).get(f"/api/v1/admin/platform/spaces/{world.lab.pk}/chat-templates")
    assert response.status_code == 200
    assert api(world.boss).get(f"/api/v1/admin/platform/spaces/{world.lab.pk}/chat-templates").status_code in {401, 403}
