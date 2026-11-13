import pytest
from apps.maker_formats.errors import FormatError
from apps.maker_formats.range_reader import BytesReader
from apps.maker_formats.registry import REGISTRY
from apps.maker_formats.validation import validate
from .samples import SAMPLES

STRONG = [("stl", "binary"), ("pdf", "pdf"), ("png", "png"), ("svg", "svg"),
          ("step", "step"), ("iges", "iges"), ("dwg", "dwg"), ("uf2", "uf2"),
          ("elf", "arm"), ("mp4", "isobmff"), ("7z", "7z"), ("zip", "archive"),
          ("3mf", "core"), ("hex", "intelhex"), ("obj", "obj"), ("gbr", "gerber")]


@pytest.mark.parametrize("source", STRONG)
@pytest.mark.parametrize("target", STRONG)
def test_strong_signature_wrong_extension_cross_product(source, target):
    if source == target or (source == ("3mf", "core") and target == ("zip", "archive")):
        return  # A real 3MF is also a structurally safe generic ZIP.
    with pytest.raises(FormatError):
        validate(BytesReader(SAMPLES[source]()), REGISTRY[target])
