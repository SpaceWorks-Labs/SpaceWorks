import pytest
from apps.maker_formats.errors import FormatError
from apps.maker_formats.range_reader import BytesReader
from apps.maker_formats.upload_policy import upload_spec, validate_upload
from .samples import binary_stl


def test_g1_coarse_model_example_classifies_content_without_extension_fallback():
    spec, cap, group = upload_spec("project.stl", group="model", subtype="auto", declared_mime="model/stl")
    assert group == "fab-3dprint" and spec.extension == "stl"
    result, _ = validate_upload(BytesReader(binary_stl(True)), extension="stl", group=group, subtype="auto", effective_cap=cap)
    assert result.subtype == "binary"
    with pytest.raises(FormatError):
        validate_upload(BytesReader(b"MZbad"), extension="stl", group=group, subtype="auto", effective_cap=cap)


def test_declared_ambiguous_slot_is_not_guessed_across_groups():
    with pytest.raises(FormatError):
        upload_spec("archive.zip", group="model", subtype="auto", declared_mime="application/zip")
