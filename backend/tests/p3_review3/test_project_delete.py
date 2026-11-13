import pytest
from django.db import transaction

from apps.presence import services
from apps.presence.display import tv_payload
from apps.presence.models import PresenceSettings

pytestmark = pytest.mark.django_db


@pytest.mark.parametrize("queryset_delete", [False, True])
def test_deleting_imageless_displayed_project_invalidates_cached_title(lane, queryset_delete):
    session = services.start_session(lane.owner, lane.space, 60, latitude=0, longitude=0,
                                    status="working", project_id=lane.project.pk)
    assert not lane.project.image_key
    assert tv_payload(lane.space)[0]["project_title"] == lane.project.title
    before = PresenceSettings.objects.get(makerspace=lane.space).display_version
    if queryset_delete:
        type(lane.project).objects.filter(pk=lane.project.pk).delete()
    else:
        lane.project.delete()
    session.refresh_from_db()
    assert session.account_project_id is None
    assert PresenceSettings.objects.get(makerspace=lane.space).display_version != before
    assert "project_title" not in tv_payload(lane.space)[0]


def test_project_delete_rollback_preserves_display_generation_and_title(lane):
    services.start_session(lane.owner, lane.space, 60, latitude=0, longitude=0,
                          status="working", project_id=lane.project.pk)
    before = PresenceSettings.objects.get(makerspace=lane.space).display_version
    payload = tv_payload(lane.space)
    with pytest.raises(RuntimeError), transaction.atomic():
        lane.project.delete()
        raise RuntimeError("Roll back the delete")
    assert PresenceSettings.objects.get(makerspace=lane.space).display_version == before
    assert tv_payload(lane.space) == payload

