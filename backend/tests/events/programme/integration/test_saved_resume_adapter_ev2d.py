from hashlib import sha256
from types import SimpleNamespace

import pytest

from apps.events.contracts import saved_resume_registration as adapter
from apps.events.submissions.errors import SubmissionError


class Targets:
    def __init__(self, present=True):
        self.present = present

    def filter(self, **kwargs):
        assert kwargs["verification_key"] == "owned-verification-key"
        assert kwargs["member_id"] == 7 and kwargs["state"] == "copying"
        return self

    def exists(self):
        return self.present


def prepared(content, *, digest=None):
    return adapter.PreparedResume(7, 11, 3, len(content), digest or sha256(content).hexdigest(),
                                  SimpleNamespace(chunks=iter([content])))


def test_resume_copy_refuses_foreign_target_before_storage(monkeypatch):
    monkeypatch.setattr(adapter, "HackathonParticipantAsset", SimpleNamespace(objects=Targets(False)))
    provider = adapter.SavedResumeProvider(None)
    with pytest.raises(SubmissionError) as error:
        provider.copy_to_event(prepared=prepared(b"pdf"), event_id=2, asset_id=3,
                               target_key="owned-verification-key")
    assert error.value.status_code == 404


def test_resume_stream_hash_mismatch_cannot_create_event_bytes(monkeypatch):
    monkeypatch.setattr(adapter, "HackathonParticipantAsset", SimpleNamespace(objects=Targets()))
    with pytest.raises(SubmissionError) as error:
        adapter.SavedResumeProvider(None).copy_to_event(prepared=prepared(b"pdf", digest="0"*64),
            event_id=2, asset_id=3, target_key="owned-verification-key")
    assert error.value.status_code == 409


def test_saved_selection_revoked_during_storage_write_cannot_publish(monkeypatch):
    monkeypatch.setattr(adapter, "HackathonParticipantAsset", SimpleNamespace(objects=Targets()))
    from apps.events.submissions import storage_promotion
    from apps.accounts.saved_details.errors import SavedDetailsError
    writes = []
    monkeypatch.setattr(storage_promotion, "promote", lambda *a, **kw: writes.append(kw))
    def revoked(**kwargs):
        raise SavedDetailsError("saved_detail_changed", "Review the saved selection.", 409)
    monkeypatch.setattr(adapter, "prepare_saved_resume_selection", revoked)
    with pytest.raises(SavedDetailsError):
        adapter.SavedResumeProvider(None).copy_to_event(prepared=prepared(b"pdf"), event_id=2,
            asset_id=3, target_key="owned-verification-key")
    assert len(writes) == 1 and writes[0]["target_key"] == "owned-verification-key"
