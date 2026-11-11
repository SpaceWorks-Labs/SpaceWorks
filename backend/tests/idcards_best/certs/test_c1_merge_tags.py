"""C1: kind/award/role/place merge tags, the real crewRole, kind-named title and notices."""
from types import SimpleNamespace

import pytest
from rest_framework.exceptions import ValidationError

from apps.events.certificates.layout import normalize_document
from apps.events.certificates.merge import (document_title, frozen_merge, issuance_merge, kind_title,
                                            merge_values, ordinal, sample_merge)
from apps.events.notification_envelopes import certificate_copy

from .helpers import attended_certificate


@pytest.mark.parametrize("number,expected", [(1, "1st"), (2, "2nd"), (3, "3rd"), (4, "4th"), (11, "11th"),
                                             (12, "12th"), (13, "13th"), (21, "21st"), (22, "22nd"),
                                             (23, "23rd"), (101, "101st"), (111, "111th"), (112, "112th")])
def test_ordinals(number, expected):
    assert ordinal(number) == expected


def _doc(text, badge=False):
    return {"version": 2, "page_width_mm": 297 if not badge else 85.6, "page_height_mm": 210 if not badge else 53.98,
            "layers": [{"id": "6f1c2a9e-1b2c-4d5e-8f90-123456789abc", "order": 0, "type": "text", "x_mm": 1,
                        "y_mm": 1, "width_mm": 50, "height_mm": 10, "rotation": 0, "text": text}]}


def test_new_tags_are_certificate_only_and_old_tags_still_work():
    normalize_document(_doc("{{kind}} · {{award}} · {{role}} · {{place}} · {{crewRole}} {{name}}"))
    normalize_document(_doc("{{name}} {{crewRole}}", badge=True), badge=True)
    with pytest.raises(ValidationError):
        normalize_document(_doc("{{award}}", badge=True), badge=True)
    with pytest.raises(ValidationError):
        normalize_document(_doc("{{email}}"))


@pytest.mark.django_db(transaction=True)
def test_issuance_freezes_labels_and_crew_role_carries_the_real_role():
    event, member, row = attended_certificate("c1-freeze")
    assert row.layout_snapshot["merge"] == {"kind": "Attendance", "award": "", "role": "Attendee", "place": ""}
    values = merge_values(row)
    assert values["kind"] == "Attendance" and values["role"] == "Attendee" and values["crewRole"] == "Attendee"
    assert document_title(row) == f"Certificate of attendance {row.serial}"


@pytest.mark.django_db(transaction=True)
def test_rows_issued_before_frozen_labels_keep_their_bytes():
    event, member, row = attended_certificate("c1-legacy")
    legacy = SimpleNamespace(**{**{f: getattr(row, f) for f in (
        "recipient_name", "event_title", "event_starts_at", "issuer_name", "issued_at", "serial",
        "event_timezone_name", "kind", "award_id")}, "layout_snapshot": {}})
    assert merge_values(legacy)["crewRole"] == ""
    assert document_title(legacy) == f"Attendance certificate {row.serial}"
    assert frozen_merge(legacy)["kind"] == "Attendance"


@pytest.mark.django_db(transaction=True)
def test_pdf_title_names_the_kind():
    from apps.events.certificate_rendering import render_certificate_pdf
    event, member, row = attended_certificate("c1-title")
    assert b"Certificate of attendance" in render_certificate_pdf(row)


def test_samples_and_titles_cover_every_kind():
    from apps.events.models_certificates import EventAttendanceCertificate
    for kind in EventAttendanceCertificate.Kind.values:
        assert kind_title(kind) and sample_merge(kind)["kind"]
    assert sample_merge("winner") == {"kind": "Winner", "award": "1st place · Best hardware hack",
                                      "role": "Participant", "place": "1st place"}


def test_notification_copy_names_the_kind():
    subject, text = certificate_copy(SimpleNamespace(kind="mentor_thanks"), "certificate_ready", "Hack night")
    assert subject == "Your mentor thank-you certificate is ready"
    assert text == "Your mentor thank-you certificate for Hack night is ready to download."
    subject, _ = certificate_copy(SimpleNamespace(kind="winner"), "certificate_revoked", "Hack night")
    assert subject == "Your winner's certificate was withdrawn"


@pytest.mark.django_db(transaction=True)
def test_role_merge_for_registration_kinds():
    event, member, row = attended_certificate("c1-roles")
    merge = issuance_merge(event_id=event.pk, kind="participant", member_id=member.pk,
                           subject_kind="registration", subject_id=row.registration_id)
    assert merge == {"kind": "Participant", "award": "", "role": "Participant", "place": ""}


@pytest.mark.django_db(transaction=True)
@pytest.mark.parametrize("kind,rank,award,place", [
    ("winner", 1, "1st place · Best design", "1st place"),
    ("finalist", 12, "12th place · Best design", "12th place"),
    ("finalist", None, "Finalist · Best design", ""),
])
def test_award_labels_with_ordinal_place(monkeypatch, kind, rank, award, place):
    from apps.events.certificates import merge as merge_module
    from apps.events.judging.models_definitions import HackathonPrize
    event, member, row = attended_certificate(f"c1-award-{kind}-{rank}")
    prize = HackathonPrize.objects.create(event=event, name="Best design")
    monkeypatch.setattr(merge_module, "_place", lambda **kwargs: rank)
    value = issuance_merge(event_id=event.pk, kind=kind, member_id=member.pk, subject_kind="registration",
                           subject_id=row.registration_id, award_id=prize.pk, result_revision_id=1)
    assert value == {"kind": kind.title(), "award": award, "role": "Participant", "place": place}
