"""Local real-tool export checks for the #176 format matrix."""
from pathlib import Path

import pytest

from apps.maker_formats.errors import FormatError
from apps.maker_formats.range_reader import BytesReader
from apps.maker_formats.registry import REGISTRY, resolve_spec
from apps.maker_formats.upload_policy import validate_upload
from apps.maker_formats.validation import validate


SAMPLES = Path(__file__).with_name("real_samples")
CASES = (
    ("fab-2d/plate.svg", "svg", "image/svg+xml"),
    ("fab-2d/plate.dxf", "ascii", "image/vnd.dxf"),
    ("fab-3dprint/plate.stl", "binary", "model/stl"),
    ("fab-3dprint/plate.obj", "obj", "model/obj"),
    ("fab-3dprint/bambu-plate.3mf", "bambu", "model/3mf"),
    ("fab-3dprint/bambu-plate.gcode.3mf", "sliced", "model/3mf"),
    ("fab-3dprint/bambu-plate.gcode", "gcode", "text/x.gcode"),
    ("fab-3dprint/prusaslicer-plate.bgcode", "bgcode", "application/x-bgcode"),
    ("firmware/blink.elf", "avr", "application/x-elf"),
    ("firmware/blink.hex", "intelhex", "text/x-hex"),
    ("firmware/blink-pico.uf2", "uf2", "application/x-uf2"),
    ("hardware-cad/plate.FCStd", "freecad", "application/zip"),
    ("hardware-cad/plate.step", "step", "model/step"),
    ("hardware-cad/plate.iges", "iges", "model/iges"),
    ("hardware-pcb/probe.kicad_pcb", "kicad_pcb", "text/plain"),
    ("hardware-pcb/probe-F_Cu.gbr", "gerber", "application/vnd.gerber"),
    ("hardware-pcb/probe-B_Cu.gbr", "gerber", "application/vnd.gerber"),
    ("hardware-pcb/probe-Edge_Cuts.gbr", "gerber", "application/vnd.gerber"),
    ("hardware-pcb/probe.drl", "excellon", "application/x-excellon"),
    ("hardware-pcb/probe-gerbers.zip", "gerber", "application/zip"),
)


@pytest.mark.parametrize("relative,subtype,mime", CASES, ids=[case[0] for case in CASES])
def test_real_tool_export(relative, subtype, mime):
    sample = SAMPLES / relative
    group = sample.parent.name
    spec, cap = resolve_spec(sample.name, group=group, subtype=subtype, declared_mime=mime)
    reader = BytesReader(sample.read_bytes())
    result = validate(reader, spec, effective_cap=cap)
    uploaded, chosen = validate_upload(
        reader, extension=spec.extension, group=group, subtype=subtype, effective_cap=cap,
    )
    assert uploaded == result
    assert chosen == spec
    if subtype == "kicad_pcb":
        assert result.preview == "download"


@pytest.mark.parametrize("delimiter", [b" ", b"\n", b"\r\n", b"\t"])
def test_kicad_root_token_accepts_whitespace_delimiter(delimiter):
    spec = REGISTRY["kicad_pcb", "kicad_pcb"]
    sample = BytesReader(b"(kicad_pcb" + delimiter + b"(version 20260206))")
    assert validate(sample, spec).preview == "download"


@pytest.mark.parametrize("suffix", [b"_extra ", b"extra\n", b"(", b")"])
def test_kicad_root_token_refuses_lookalike_names(suffix):
    spec = REGISTRY["kicad_pcb", "kicad_pcb"]
    with pytest.raises(FormatError, match="text_subtype_mismatch"):
        validate(BytesReader(b"(kicad_pcb" + suffix + b"(version 20260206))"), spec)
