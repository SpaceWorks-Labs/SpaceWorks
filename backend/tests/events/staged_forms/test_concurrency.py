"""Two real connections serialize the last stage-file reservation on Event."""
from concurrent.futures import ThreadPoolExecutor
from threading import Barrier
import pytest
from django.db import close_old_connections
from apps.payments.event_payouts.errors import PayoutError
from apps.events.staged_forms.upload_models import StageFormAsset
from .test_uploads import stage_upload, create_file

pytestmark = pytest.mark.django_db(transaction=True)


def test_last_event_quota_cannot_be_reserved_twice(stage_upload, settings):
    env, row, assignment, _ = stage_upload
    settings.EVENT_STAGE_EVENT_QUOTA_BYTES = 128
    barrier = Barrier(2)
    def reserve(_):
        close_old_connections()
        try:
            barrier.wait(timeout=10)
            create_file(env, row, assignment)
            return "reserved"
        except PayoutError as exc:
            return str(exc.detail["code"])
        finally:
            close_old_connections()
    with ThreadPoolExecutor(max_workers=2) as executor:
        outcomes = list(executor.map(reserve, range(2)))
    assert sorted(outcomes) == ["reserved", "stage_file_quota"]
    assert StageFormAsset.objects.count() == 1
