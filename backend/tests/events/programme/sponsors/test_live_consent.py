"""The same live predicate protects new requests and already-open bounded streams."""

from dataclasses import replace
from datetime import timedelta
from types import SimpleNamespace
from unittest.mock import Mock

import pytest
from django.http import Http404
from django.utils import timezone

from apps.events.judging import sponsor_consent_workflow as consent
from apps.events.judging import sponsors
from apps.events.judging.errors import ProgrammeError
from apps.events.judging.ports import ParticipantAsset, Snapshot, Sponsor


def setup_live(monkeypatch):
    asset = ParticipantAsset(id=301, event_id=42, member_id=17, sha256="a" * 64,
        state="ready", current=True, expires_at=timezone.now() + timedelta(days=1))
    snapshot = Snapshot(id=101, event_id=42, team_id=21, member_ids=(17,), track_ids=(7,), prize_ids=(),
        title="Sensor", description="Hardware project", content_sha256="b" * 64, eligible=True, current=True,
        metadata_public=False, public_asset_ids=(), public_links=(), expires_at=asset.expires_at)
    sponsor = Sponsor(id=6, event_id=42, name="Maker Partner", active=True, track_ids=(7,))
    row = SimpleNamespace(asset_sha256=asset.sha256, expires_at=asset.expires_at, state="granted")
    member = SimpleNamespace(pk=17, is_authenticated=True, is_active=True, access_status="active", account_kind="member")
    event = SimpleNamespace(pk=42)
    ports = Mock()
    ports.participant_asset.side_effect = lambda _: asset
    ports.sponsor.return_value = sponsor
    ports.snapshots.return_value = (snapshot,)
    ports.sponsor_rep_tracks.return_value = (7,)
    model = Mock()
    model.objects.filter.return_value.first.side_effect = lambda: row if row.state == "granted" else None
    monkeypatch.setattr(consent, "ParticipantSponsorResumeConsent", model)
    user_model = Mock()
    user_model.objects.filter.return_value.first.return_value = member
    monkeypatch.setattr(consent, "get_user_model", lambda: user_model)
    monkeypatch.setattr("django.contrib.auth.get_user_model", lambda: user_model)
    # Event lookup is needed even for direct B policy calls, not just HTTP routes.
    from apps.events.models import Event
    monkeypatch.setattr(Event.objects, "select_related", Mock(return_value=Mock(filter=Mock(return_value=Mock(first=Mock(return_value=event))))))
    monkeypatch.setattr(consent, "runtime", lambda: ports)
    monkeypatch.setattr(sponsors, "runtime", lambda: ports)
    monkeypatch.setattr(sponsors.event_authority, "can", lambda *args: True)
    return ports, row, asset, snapshot, event, member


def effective():
    consent.require_effective_for_asset(event_id=42, member_id=17, sponsor_id=6, asset_id=301, purpose="recruiting")


def test_contributor_without_a_matching_frozen_submission_remains_ineligible(monkeypatch):
    ports, *_ = setup_live(monkeypatch)
    ports.snapshots.return_value = ()
    with pytest.raises(Http404):
        effective()


@pytest.mark.parametrize("change", ["revoke", "hash", "replace", "foreign_track", "sponsor_inactive", "private_gate", "suspended"])
def test_effective_consent_rechecks_every_authority_boundary(monkeypatch, change):
    ports, row, asset, snapshot, _, member = setup_live(monkeypatch)
    effective()
    if change == "revoke":
        row.state = "revoked"
    elif change == "hash":
        ports.participant_asset.side_effect = None
        ports.participant_asset.return_value = replace(asset, sha256="c" * 64)
    elif change == "replace":
        ports.participant_asset.side_effect = None
        ports.participant_asset.return_value = replace(asset, current=False)
    elif change == "foreign_track":
        ports.snapshots.return_value = (replace(snapshot, track_ids=(8,)),)
    elif change == "sponsor_inactive":
        ports.sponsor.return_value = replace(ports.sponsor.return_value, active=False)
    elif change == "private_gate":
        ports.require_programme.side_effect = Http404
    elif change == "suspended":
        member.access_status = "suspended"
    with pytest.raises(Http404):
        effective()


def test_expiry_is_410_only_after_otherwise_authorized_consent(monkeypatch):
    ports, row, asset, *_ = setup_live(monkeypatch)
    ports.participant_asset.side_effect = None
    ports.participant_asset.return_value = replace(asset, state="expired", expires_at=timezone.now() - timedelta(seconds=1))
    with pytest.raises(ProgrammeError) as error:
        effective()
    assert error.value.status_code == 410
    row.state = "revoked"
    with pytest.raises(Http404):
        effective()


def test_preissued_stream_stops_after_owner_revocation(monkeypatch):
    ports, row, _, _, event, member = setup_live(monkeypatch)

    def stream(**kwargs):
        def chunks():
            for chunk in (b"first", b"second"):
                kwargs["reauthorize"]()
                yield chunk
        return chunks()
    ports.stream_asset.side_effect = stream
    download = sponsors.resume_download(member, event, 6, 301, object())
    assert next(download) == b"first"
    row.state = "revoked"
    with pytest.raises(Http404):
        next(download)


def test_rep_track_revocation_blocks_a_url_issued_while_consent_was_valid(monkeypatch):
    ports, _, _, _, event, member = setup_live(monkeypatch)
    ports.stream_asset.side_effect = lambda **kwargs: kwargs["reauthorize"]
    previously_issued = sponsors.resume_download(member, event, 6, 301, object())
    ports.sponsor_rep_tracks.return_value = ()
    with pytest.raises(Http404):
        previously_issued()


def test_locked_internal_writer_cannot_be_called_with_an_http_constructed_context(monkeypatch):
    from apps.events.contracts.providers import LockedContext
    from apps.events.judging.boundary import assert_locked
    with pytest.raises(RuntimeError):
        assert_locked(LockedContext(event_id=42, tenant_ids=(9,), account_ids=(17,)))
