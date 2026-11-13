"""Authenticate old AAD and rebind live + historical sources on tenant remap."""

import secrets

import pytest

from apps.encryption.crypto import PiiAuthenticationFailed, decrypt, encrypt
from apps.events.answer_derivations import portability
from apps.events.answer_derivations.models import EventAnswerDerivation


def test_tenant_remap_rebinds_source_and_reopen_history(monkeypatch):
    old_dek, new_dek = secrets.token_bytes(32), secrets.token_bytes(32)
    table = EventAnswerDerivation._meta.db_table

    def old_envelope(value, field):
        return encrypt(value.encode(), old_dek, key_version=1, makerspace_id=9, table=table, pk=19, field=field)

    record = {name: None for name in portability.PORTABLE_FIELDS}
    record.update(id=19, event_id=42, role_assignment_id=81, question_id="age", version=2,
                  source_dob_envelope=old_envelope("2003-05-12", "source_dob_envelope"), source_history=[{
                      "source_dob_envelope": old_envelope("2004-05-12", "source_dob_envelope"),
                      "reason_envelope": old_envelope("Owner correction", "reopen_reason_envelope"),
                      "event_date_revision": 7, "as_of_date": "2026-12-01", "locked_at": "2026-10-18T00:00:00Z", "version": 1,
                  }])
    monkeypatch.setattr(portability, "require_preparation_boundary", lambda: None)
    monkeypatch.setattr(portability, "prepared_key", lambda tenant_id: (4, new_dek))
    remapped = portability.rebind_portable_envelopes(
        record, source_makerspace_id=9, target_makerspace_id=29, target_pk=119,
        source_key_loader=lambda version: old_dek,
    )
    assert remapped["id"] == 119 and "2003-05-12" not in str(remapped)
    assert decrypt(remapped["source_dob_envelope"], new_dek, makerspace_id=29, table=table, pk=119, field="source_dob_envelope") == b"2003-05-12"
    assert decrypt(remapped["source_history"][0]["source_dob_envelope"], new_dek, makerspace_id=29, table=table, pk=119, field="source_dob_envelope") == b"2004-05-12"
    assert decrypt(remapped["source_history"][0]["reason_envelope"], new_dek, makerspace_id=29, table=table, pk=119, field="reopen_reason_envelope") == b"Owner correction"
    assert record["id"] == 19
    with pytest.raises(PiiAuthenticationFailed):
        decrypt(remapped["source_dob_envelope"], new_dek, makerspace_id=9, table=table, pk=19, field="source_dob_envelope")
