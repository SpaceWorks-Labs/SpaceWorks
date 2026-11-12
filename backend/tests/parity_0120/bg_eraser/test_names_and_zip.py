"""File-name normalisation, matching order, and the upload / zip guards of the bulk photo upload."""
import zipfile
from io import BytesIO

import pytest
from django.core.files.uploadedfile import SimpleUploadedFile
from rest_framework.exceptions import ValidationError

from apps.card_designs import photo_batch_intake as intake
from apps.card_designs.photo_names import HolderIndex, collapse, stem, tokens

from .conftest import jpeg

HOLDERS = [
    {"id": 1, "name": "Priya Raman", "number": "TNK-0042", "email": "priya.raman@example.org"},
    {"id": 2, "name": "José Álvarez", "number": "TNK-0043", "email": "jose@example.org"},
    {"id": 3, "name": "Sam Lee", "number": "TNK-0044", "email": "sam.l@example.org"},
    {"id": 4, "name": "Sam Lee", "number": "TNK-0045", "email": "sam.lee2@example.org"},
]
INDEX = HolderIndex(HOLDERS)
# "priya.raman@" collapses to the same string as the name "Priya Raman", and the email level wins by design.
NAME_INDEX = HolderIndex([{**HOLDERS[0], "email": ""}, *HOLDERS[1:]])


def test_names_are_normalised_for_case_separators_extension_and_diacritics():
    assert stem("C:\\photos\\Priya_Raman.JPG") == "Priya_Raman"
    assert tokens("  José--Álvarez_ ") == ("jose", "alvarez")
    assert collapse("TNK-0042") == "tnk0042"


@pytest.mark.parametrize("filename", ["Priya Raman.jpg", "priya_raman.JPEG", "PRIYA-RAMAN.png", "raman priya.webp"])
def test_full_name_matches_in_any_case_separator_and_order(filename):
    assert NAME_INDEX.match(filename) == ("name", [1])


def test_diacritics_fold_both_ways():
    assert INDEX.match("jose alvarez.jpg") == ("name", [2])
    assert INDEX.match("José Álvarez.jpg") == ("name", [2])


@pytest.mark.parametrize("filename", ["TNK-0042.jpg", "tnk_0042.png", "TNK 0042.jpg", "tnk0042.jpeg"])
def test_a_card_number_file_matches_directly(filename):
    assert INDEX.match(filename) == ("number", [1])


def test_number_as_leading_tokens_beats_the_name_in_the_same_file_name():
    assert INDEX.match("TNK-0043 something else.jpg") == ("number", [2])
    # The number wins even when the rest of the name belongs to someone else.
    assert INDEX.match("tnk-0042 jose alvarez.jpg") == ("number", [1])


def test_email_local_part_and_whole_address_match_before_the_name():
    assert INDEX.match("priya.raman.jpg") == ("email", [1])
    assert INDEX.match("jose@example.org.jpg") == ("email", [2])
    assert INDEX.match("sam.l.jpg") == ("email", [3])


def test_a_shared_name_is_ambiguous_and_lists_every_candidate():
    assert INDEX.match("Sam Lee.jpg") == ("name", [3, 4])


def test_nothing_that_fits_is_unmatched():
    assert INDEX.match("IMG_20261104.jpg") == ("", [])
    assert INDEX.match("....jpg") == ("", [])


def _upload(name, data):
    return SimpleUploadedFile(name, data)


def _zip(entries, **kwargs):
    buffer = BytesIO()
    with zipfile.ZipFile(buffer, "w", zipfile.ZIP_DEFLATED, **kwargs) as archive:
        for name, data in entries:
            archive.writestr(name, data)
    return _upload("photos.zip", buffer.getvalue())


def test_files_and_a_zip_are_read_with_non_images_skipped():
    result = intake.read_uploads([_upload("a.jpg", jpeg()), _upload("notes.txt", b"x"),
                                  _zip([("sub/Priya Raman.jpg", jpeg()), ("__MACOSX/._x.jpg", jpeg()),
                                        (".hidden.jpg", jpeg()), ("readme.md", b"hi"), ("dir/", b"")])])
    assert [name for name, _ in result.photos] == ["a.jpg", "Priya Raman.jpg"]
    assert result.skipped == 2  # notes.txt and readme.md


def test_the_batch_cap_is_enforced_for_files_and_for_zip_entries(monkeypatch):
    monkeypatch.setattr(intake, "MAX_FILES", 2)
    with pytest.raises(ValidationError):
        intake.read_uploads([_upload(f"{n}.jpg", jpeg()) for n in range(3)])
    with pytest.raises(ValidationError):
        intake.read_uploads([_zip([(f"{n}.jpg", jpeg()) for n in range(3)])])
    with pytest.raises(ValidationError):
        intake.read_uploads([_upload("1.jpg", jpeg())], existing=2)


def test_zip_guards_nested_archives_encryption_entry_count_and_total_size(monkeypatch):
    with pytest.raises(ValidationError):
        intake.read_uploads([_zip([("inner.zip", b"PK\x03\x04junk")])])
    with pytest.raises(ValidationError):  # an archive hiding behind an image name, caught by its magic bytes
        intake.read_uploads([_zip([("a.jpg", b"PK\x03\x04" + b"0" * 50)])])
    monkeypatch.setattr(intake, "MAX_ZIP_ENTRIES", 3)
    with pytest.raises(ValidationError):
        intake.read_uploads([_zip([(f"{n}.jpg", jpeg()) for n in range(4)])])
    monkeypatch.setattr(intake, "MAX_ZIP_ENTRIES", 2000)
    monkeypatch.setattr(intake, "MAX_ZIP_UNCOMPRESSED", 100)
    with pytest.raises(ValidationError):
        intake.read_uploads([_zip([("a.jpg", jpeg()), ("b.jpg", jpeg())])])


def test_zip_bomb_ratio_and_oversize_entries_are_refused(monkeypatch):
    bomb = _zip([("a.jpg", b"\x00" * 3_000_000)])  # compresses ~3000:1
    with pytest.raises(ValidationError):
        intake.read_uploads([bomb])
    monkeypatch.setattr(intake, "MAX_UPLOAD_BYTES", 10)
    with pytest.raises(ValidationError):
        intake.read_uploads([_zip([("a.jpg", jpeg())])])


def test_a_corrupt_zip_and_an_empty_upload_are_refused():
    with pytest.raises(ValidationError):
        intake.read_uploads([_upload("bad.zip", b"this is not a zip")])
    with pytest.raises(ValidationError):
        intake.read_uploads([])
    with pytest.raises(ValidationError):
        intake.read_uploads([_upload("a.tar.gz", b"x")])


def test_an_oversize_single_photo_is_kept_as_an_empty_unreadable_entry(monkeypatch):
    monkeypatch.setattr(intake, "MAX_UPLOAD_BYTES", 10)
    result = intake.read_uploads([_upload("big.jpg", b"x" * 50)])
    assert result.photos == [("big.jpg", b"")]
