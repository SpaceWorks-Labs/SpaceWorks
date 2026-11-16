from .errors import FormatError
from .registry import GERBER_EXTENSIONS
from .zip_listing import list_zip


def check_zip(reader, spec):
    entries = list_zip(reader)
    names = {entry.name.lower() for entry in entries}
    subtype, extension = spec.subtype, spec.extension
    valid = False
    if extension in {"3mf", "gcode.3mf"}:
        base = {"[content_types].xml", "_rels/.rels"} <= names
        base &= any(n.startswith("3d/") and n.endswith(".model") for n in names)
        found = "core"
        if any(n.startswith("metadata/slic3r_pe") for n in names):
            found = "prusa"
        if "metadata/project_settings.config" in names:
            found = "orca" if any("orca" in n for n in names) else "bambu"
        if any(n.startswith("metadata/plate_") and n.endswith(".gcode") for n in names):
            found = "sliced"
        valid = base and found == subtype
    elif extension == "zip":
        suffixes = set(GERBER_EXTENSIONS.split()) | {"drl", "xln"}
        valid = subtype in {"archive", "source"} or any(n.rsplit(".", 1)[-1] in suffixes for n in names)
    elif extension == "fcstd":
        valid = "document.xml" in names
    elif extension == "amf":
        valid = any(n.endswith(".amf") for n in names)
    elif extension == "fzz":
        valid = any(n.endswith(".fz") for n in names)
    elif extension == "pptx":
        valid = "ppt/presentation.xml" in names
    elif extension == "odp":
        valid = "mimetype" in names and "content.xml" in names
    elif extension == "epro":
        valid = any(n.endswith((".epru", ".esch", ".epcb")) for n in names)
    elif extension == "cdr":
        valid = any(n.startswith("content/") for n in names)
    elif extension == "f3d":
        valid = any(n.endswith((".f3d", ".smb", ".json")) for n in names)
    if not valid:
        raise FormatError("container_subtype_mismatch")
    return entries
