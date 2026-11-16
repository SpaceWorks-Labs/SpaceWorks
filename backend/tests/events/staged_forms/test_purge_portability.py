"""Independent stage retention survives R removal and authorized Events purge."""
from datetime import timedelta
import pytest
from django.db import transaction, connection
from apps.events.staged_forms.purge import preflight, delete_locked
from apps.events.staged_forms.retention import cleanup_one
from apps.events.staged_forms.upload_models import StageFileCleanup, StageFormAsset
from apps.events.staged_forms.response_models import StageFormAssignment
from .test_uploads import stage_upload, create_file

pytestmark = pytest.mark.django_db(transaction=True)


def test_reimbursement_purge_does_not_delete_stage_rows(stage_upload):
    env, row, assignment, _ = stage_upload
    create_file(env, row, assignment)
    assert preflight(makerspace=env.space, module_key="event_reimbursements") == {"stage_rows": "preserved"}
    with transaction.atomic():
        assert delete_locked(makerspace=env.space, module_key="event_reimbursements") == (0, frozenset())
    assert StageFormAssignment.objects.filter(pk=assignment.pk).exists()
    assert StageFormAsset.objects.count() == 1


def test_events_purge_preserves_cleanup_and_retries_after_rows_disappear(stage_upload):
    env, row, assignment, _ = stage_upload
    created = create_file(env, row, assignment)
    asset = StageFormAsset.objects.get(pk=created["asset_id"])
    with transaction.atomic(), connection.cursor() as cursor:
        cursor.execute("SET LOCAL app.allow_immutable_delete = 'on'")
        delete_locked(makerspace=env.space, module_key="events")
    assert not StageFormAsset.objects.exists()
    cleanup = StageFileCleanup.objects.get(source_asset_id=asset.pk)
    class Store:
        def delete(self, keys):
            assert set(keys) == {asset.staging_key, asset.object_key}
    assert cleanup_one(cleanup.pk, store=Store())
    cleanup.refresh_from_db()
    assert cleanup.last_deleted_at and StageFileCleanup.objects.filter(pk=cleanup.pk).exists()


def test_missing_cleanup_locator_blocks_all_stage_deletion(stage_env):
    # New imports must register target locators before publishing; the preflight
    # refuses a missing locator rather than silently relying on best-effort S3.
    from .conftest import definition, participant
    from .test_inline_submission import outer
    from apps.events.staged_forms.stage_workflow import activate_locked
    from apps.events.staged_forms.trigger_service import Participant
    env = stage_env
    registration, application = participant(env)
    row = definition(env)
    with outer(env) as (event, locks):
        assignment = activate_locked(definition=row, subject=Participant(event, env.owner.pk, registration, application), locks=locks)
    StageFormAsset.objects.create(event=env.event, assignment=assignment, owner_member=env.owner,
        form_revision=row.current_revision, question_id="old", expected_bytes=1, declared_mime="image/png",
        original_filename="old.png", staging_key="legacy/staging", object_key="legacy/final", scanner_policy="none")
    with pytest.raises(ValueError, match="locators"):
        preflight(makerspace=env.space, module_key="events")
    assert StageFormAssignment.objects.filter(pk=assignment.pk).exists()
