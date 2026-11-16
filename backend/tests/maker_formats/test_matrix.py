import pytest

from apps.maker_formats.errors import FormatError
from apps.maker_formats.range_reader import BytesReader
from apps.maker_formats.registry import REGISTRY, extension_from_name, resolve_spec
from apps.maker_formats.validation import validate
from .samples import SAMPLES


def test_complete_extension_and_content_subtype_inventory():
    assert set(REGISTRY) == set(SAMPLES)


@pytest.mark.parametrize("key", sorted(SAMPLES))
def test_every_alias_and_subtype_has_a_structural_positive(key):
    spec = REGISTRY[key]
    result = validate(BytesReader(SAMPLES[key]()), spec)
    assert result.subtype == key[1]
    assert result.mime


@pytest.mark.parametrize("key", sorted(SAMPLES))
def test_every_format_refuses_empty_and_effective_cap_plus_one(key):
    spec = REGISTRY[key]
    with pytest.raises(FormatError, match="empty_file"):
        validate(BytesReader(b""), spec)
    with pytest.raises(FormatError, match="file_too_large"):
        validate(BytesReader(SAMPLES[key]()), spec, effective_cap=1)


@pytest.mark.parametrize("key", sorted(SAMPLES))
@pytest.mark.parametrize("bad", [b"MZpayload", b"\xcf\xfa\xed\xfepayload", b"<?php echo(1);", b"<html><script/>", b"#!/bin/sh\necho test"])
def test_universal_executable_and_active_disguises(key, bad):
    with pytest.raises(FormatError):
        validate(BytesReader(bad), REGISTRY[key])


@pytest.mark.parametrize("name", ["../a.stl", "/a.stl", "a\\b.stl", "C:a.stl", "a\0.stl", "a\n.stl",
                                  "a\u202e.stl", " a.stl", "a.stl ", ".stl", "a.stl.", "a\uff0estl"])
def test_filename_tricks(name):
    with pytest.raises(FormatError):
        extension_from_name(name)


def test_compound_suffix_and_cap_cannot_be_raised():
    assert extension_from_name("part.GCODE.3MF") == "gcode.3mf"
    assert extension_from_name("archive.tar.gz") == "tar.gz"
    spec, cap = resolve_spec("part.stl", group="fab-3dprint", subtype="binary",
                             declared_mime="application/octet-stream", event_cap=10**12)
    assert cap == spec.max_bytes
    with pytest.raises(FormatError, match="mime_mismatch"):
        resolve_spec("part.stl", group="fab-3dprint", subtype="binary", declared_mime="image/png")


def test_legacy_policy_remains_deliberately_weak_until_explicit_upgrade():
    from apps.maker_file_formats import has_required_signature
    assert has_required_signature("iges", b"IGES data")
    with pytest.raises(FormatError):
        validate(BytesReader(b"IGES data"), REGISTRY["iges", "iges"])
