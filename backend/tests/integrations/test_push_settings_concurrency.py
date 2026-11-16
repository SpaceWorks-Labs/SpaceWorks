import pytest

from apps.integrations.admin_push import PlatformPushSettingsForm
from apps.integrations.models_push import PlatformPushSettings


@pytest.mark.django_db
def test_stale_push_form_does_not_overwrite_firebase_web_settings():
    row = PlatformPushSettings.objects.create(pk=1, apns_topic="old", firebase_web_config={})
    stale = PlatformPushSettings.objects.get(pk=row.pk)
    form = PlatformPushSettingsForm(data={"apns_team_id": "", "apns_key_id": "", "apns_topic": "new"}, instance=stale)
    assert form.is_valid(), form.errors
    PlatformPushSettings.objects.filter(pk=row.pk).update(firebase_web_config={"project_id": "new-project"})
    form.save()
    row.refresh_from_db()
    assert row.apns_topic == "new"
    assert row.firebase_web_config == {"project_id": "new-project"}
