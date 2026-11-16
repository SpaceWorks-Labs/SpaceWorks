from datetime import timedelta
from types import SimpleNamespace
from unittest.mock import patch, Mock

import pytest
from django.utils import timezone

from apps.events.contracts.providers import ReadPurpose
from apps.events.submissions.errors import SubmissionError
from apps.events.submissions.read_policy import EventAssetReader
from apps.events.submissions.downloads import download_response


def asset(**values):
    data = dict(pk=301, state="ready", scan_status="clean", expired_at=None,
                expires_at=timezone.now() + timedelta(minutes=2), actual_bytes=4,
                canonical_mime="application/pdf", original_filename="a\".pdf",
                object_key="final/owned", final_version_id="v1", member_id=18)
    return SimpleNamespace(**{**data, **values})


def fixture(row, allowed, *, participant=False):
    policy = Mock()
    def require(**kwargs):
        if not allowed[0]:
            raise SubmissionError("not_found", 404)
        return (timezone.now() + timedelta(seconds=30),)
    policy.require.side_effect = require
    reader = EventAssetReader(policy=policy, bucket="private", participant=participant)
    manager = Mock()
    manager.filter.return_value.first.return_value = row
    return reader, manager


def test_old_locator_after_revoke_denies_get_head_range_before_storage():
    allowed, row = [True], asset()
    reader, manager = fixture(row, allowed, participant=True)
    with patch("apps.events.submissions.read_policy.model_for", return_value=SimpleNamespace(objects=manager)):
        reader.authorize_read(actor_id=18, asset_id=301, snapshot_id=None, purpose=ReadPurpose.SPONSOR_RESUME)
        allowed[0] = False
        for method, headers in (("GET", {}), ("HEAD", {}), ("GET", {"Range": "bytes=0-1"})):
            storage = Mock()
            with pytest.raises(SubmissionError) as caught:
                download_response(request=SimpleNamespace(method=method, headers=headers), reader=reader,
                    storage_reader=storage, actor_id=18, asset_id=301, snapshot_id=None, purpose=ReadPurpose.SPONSOR_RESUME)
            assert caught.value.status_code == 404
            storage.assert_not_called()


def test_authorized_expired_410_never_contacts_storage():
    reader, manager = fixture(asset(expired_at=timezone.now()), [True])
    with patch("apps.events.submissions.read_policy.model_for", return_value=SimpleNamespace(objects=manager)):
        storage = Mock()
        with pytest.raises(SubmissionError) as caught:
            download_response(request=SimpleNamespace(method="GET", headers={}), reader=reader, storage_reader=storage,
                actor_id=18, asset_id=301, snapshot_id=None, purpose=ReadPurpose.TEAM_ORIGINAL)
        assert caught.value.status_code == 410
        storage.assert_not_called()


def test_range_and_head_share_auth_and_safe_response_headers():
    reader, manager = fixture(asset(), [True])
    with patch("apps.events.submissions.read_policy.model_for", return_value=SimpleNamespace(objects=manager)):
        response = download_response(request=SimpleNamespace(method="HEAD", headers={"Range": "bytes=1-2"}),
            reader=reader, storage_reader=Mock(), actor_id=18, asset_id=301, snapshot_id=None, purpose=ReadPurpose.TEAM_ORIGINAL)
        assert response.status_code == 206 and response["Content-Range"] == "bytes 1-2/4"
        assert response.content == b"" and response["Cache-Control"] == "private, no-store"
        assert "%22" in response["Content-Disposition"] and response["X-Content-Type-Options"] == "nosniff"
        denied = download_response(request=SimpleNamespace(method="GET", headers={"Range": "bytes=0-1,2-3"}),
            reader=reader, storage_reader=Mock(), actor_id=18, asset_id=301, snapshot_id=None, purpose=ReadPurpose.TEAM_ORIGINAL)
        assert denied.status_code == 416 and denied["Content-Range"] == "bytes */4"


def test_policy_recheck_after_read_withholds_chunk_on_revocation():
    allowed = [True]
    reader, manager = fixture(asset(), allowed, participant=True)
    def storage(*args, **kwargs):
        allowed[0] = False
        return b"data"
    with patch("apps.events.submissions.read_policy.model_for", return_value=SimpleNamespace(objects=manager)):
        response = download_response(request=SimpleNamespace(method="GET", headers={}), reader=reader,
            storage_reader=storage, actor_id=18, asset_id=301, snapshot_id=None, purpose=ReadPurpose.SPONSOR_RESUME)
        with pytest.raises(SubmissionError):
            next(iter(response.streaming_content))
