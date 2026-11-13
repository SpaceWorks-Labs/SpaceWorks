"""Bounded ZIP central-directory policy. Never opens/decompresses an entry."""
from dataclasses import dataclass, asdict
import re
import stat
import struct
import unicodedata

from .errors import FormatError

MAX_ENTRIES = 2000
MAX_DIRECTORY = 1024 * 1024
MAX_EXPANSION = 1024 * 1024 * 1024


@dataclass(frozen=True)
class ZipEntry:
    name: str
    compressed_bytes: int
    size_bytes: int
    nested_archive: bool


def _name(raw, flags):
    try:
        value = raw.decode("utf-8" if flags & 0x800 else "cp437")
    except UnicodeError as exc:
        raise FormatError("unsafe_archive_path") from exc
    if (not value or value.startswith(("/", "\\")) or "\\" in value or ":" in value or
            any(unicodedata.category(c).startswith("C") for c in value)):
        raise FormatError("unsafe_archive_path")
    normalized = unicodedata.normalize("NFKC", value)
    if any(part in {"..", ".", ""} for part in normalized.rstrip("/").split("/")):
        raise FormatError("unsafe_archive_path")
    return normalized


def list_zip(reader):
    if reader.size < 22 or reader.read(0, 4) != b"PK\x03\x04":
        raise FormatError("invalid_zip")
    tail = reader.read(reader.size - 22, 22)
    if not tail.startswith(b"PK\x05\x06"):
        length = min(reader.size, 65557)
        tail = reader.read(reader.size - length, length)
    position = tail.rfind(b"PK\x05\x06")
    while position >= 0:
        if position + 22 <= len(tail) and position + 22 + struct.unpack_from("<H", tail, position + 20)[0] == len(tail):
            break
        position = tail.rfind(b"PK\x05\x06", 0, position)
    if position < 0 or position + 22 > len(tail):
        raise FormatError("invalid_zip")
    eocd = struct.unpack_from("<4s4H2IH", tail, position)
    _, disk, cd_disk, disk_count, count, cd_size, cd_offset, comment = eocd
    eocd_offset = reader.size - len(tail) + position
    if position + 22 + comment != len(tail) or disk or cd_disk or disk_count != count:
        raise FormatError("invalid_zip")
    if count == 65535 or 0xffffffff in (cd_size, cd_offset):
        raise FormatError("unsupported_zip64")
    if count > MAX_ENTRIES or cd_size > MAX_DIRECTORY:
        raise FormatError("archive_limit", 413)
    if count < 1 or cd_offset + cd_size != eocd_offset:
        raise FormatError("invalid_container_bounds")
    directory = reader.read(cd_offset, cd_size)
    cursor, total, compressed = 0, 0, 0
    names, spans, manifest = set(), [], []
    for _ in range(count):
        if cursor + 46 > len(directory):
            raise FormatError("invalid_zip")
        fields = struct.unpack_from("<4s6H3I5H2I", directory, cursor)
        (magic, _, needed, flags, method, _, _, crc, packed, size, name_len,
         extra_len, comment_len, start_disk, _, attrs, offset) = fields
        if magic != b"PK\x01\x02" or start_disk or needed >= 45:
            raise FormatError("unsupported_container")
        if flags & (1 | 0x40 | 0x2000) or method not in (0, 8):
            raise FormatError("unsupported_container")
        end = cursor + 46 + name_len + extra_len + comment_len
        if end > len(directory) or 0xffffffff in (packed, size, offset):
            raise FormatError("invalid_zip")
        raw_name = directory[cursor + 46:cursor + 46 + name_len]
        name = _name(raw_name, flags)
        if name.casefold() in names or stat.S_ISLNK(attrs >> 16):
            raise FormatError("unsafe_archive_path")
        names.add(name.casefold())
        if size > max(packed, 1) * 100:
            raise FormatError("archive_ratio", 413)
        total, compressed = total + size, compressed + packed
        if total > MAX_EXPANSION:
            raise FormatError("archive_limit", 413)
        if offset + 30 > cd_offset:
            raise FormatError("invalid_container_bounds")
        local = reader.read(offset, 30)
        lm, ln, lf, lc, _, _, lcrc, lp, ls, nl, el = struct.unpack("<4s5H3I2H", local)
        if lm != b"PK\x03\x04" or (ln, lf, lc) != (needed, flags, method):
            raise FormatError("inconsistent_zip")
        data_start = offset + 30 + nl + el
        data_end = data_start + packed
        if data_end > cd_offset or reader.read(offset + 30, nl) != raw_name:
            raise FormatError("inconsistent_zip")
        if not flags & 8:
            if (lcrc, lp, ls) != (crc, packed, size):
                raise FormatError("inconsistent_zip")
        else:
            if (lcrc not in (0, crc) or lp not in (0, packed) or ls not in (0, size)):
                raise FormatError("inconsistent_zip")
            if data_end + 12 > cd_offset:
                raise FormatError("inconsistent_zip")
            descriptor = reader.read(data_end, min(16, cd_offset - data_end))
            skip = 4 if descriptor[:4] == b"PK\x07\x08" else 0
            if len(descriptor) < skip + 12 or struct.unpack_from("<3I", descriptor, skip) != (crc, packed, size):
                raise FormatError("inconsistent_zip")
            data_end += skip + 12
        spans.append((offset, data_end))
        nested = bool(re.search(r"\.(zip|7z|tgz|gz|3mf|fzz|fcstd)$", name, re.I))
        manifest.append(ZipEntry(name, packed, size, nested))
        cursor = end
    spans.sort()
    if (cursor != cd_size or spans[0][0] != 0 or
            any(left[1] > right[0] for left, right in zip(spans, spans[1:]))):
        raise FormatError("inconsistent_zip")
    if total > max(compressed, 1) * 20:
        raise FormatError("archive_ratio", 413)
    return tuple(manifest)


def manifest_json(entries):
    return [asdict(entry) for entry in entries]
