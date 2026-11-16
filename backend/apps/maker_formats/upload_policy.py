"""Upload reservation before bytes exist, followed by content classification.

G1's coarse model upload example omits subtype. Explicit subtype requests remain
strict; automatic classification tries only registered variants of the declared
extension+slot, never a different extension or a generic accept-any fallback.
"""
from .errors import FormatError
from .registry import REGISTRY, extension_from_name, resolve_spec
from .validation import validate


def upload_spec(filename, *, group, subtype, declared_mime):
    extension = extension_from_name(filename)
    if group == "model":
        group = "fab-3dprint" if extension in {"stl", "obj", "3mf", "gcode.3mf"} else "hardware-cad"
    candidates = [spec for (ext, _), spec in REGISTRY.items() if ext == extension and spec.group == group]
    if not candidates:
        raise FormatError("unsupported_format")
    if subtype != "auto":
        spec, cap = resolve_spec(filename, group=group, subtype=subtype, declared_mime=declared_mime)
        return spec, cap, group
    valid = []
    for spec in candidates:
        try:
            resolve_spec(filename, group=group, subtype=spec.subtype, declared_mime=declared_mime)
            valid.append(spec)
        except FormatError:
            continue
    if not valid:
        raise FormatError("mime_mismatch")
    return valid[0], min(spec.max_bytes for spec in valid), group


def validate_upload(reader, *, extension, group, subtype, effective_cap):
    candidates = [spec for (ext, sub), spec in REGISTRY.items() if ext == extension
                  and spec.group == group and (subtype == "auto" or subtype == sub)]
    for spec in candidates:
        try:
            return validate(reader, spec, effective_cap=effective_cap), spec
        except FormatError as exc:
            if exc.status >= 500 or exc.status == 413:
                raise
    raise FormatError("content_subtype_mismatch")
