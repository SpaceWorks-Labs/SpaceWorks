"""Turn an upload (image files and/or one zip) into a bounded list of named photos (D314c addendum).

Guards, all enforced before anything is stored: each photo <= the card-photo size limit (8 MB); at most
`MAX_FILES` photos per batch (oversized placeholders included); one zip and `MAX_REQUEST_BYTES` per upload; a zip is read in memory entry by entry, never extracted to disk, with a cap on its
entry count, its total UNCOMPRESSED size, each entry's compression ratio, no encrypted entries and no nested
archives (by name or by magic bytes). Directories, hidden and `__MACOSX` entries and non-image files are skipped
and counted; only the base name of an entry is ever used.
"""
import zipfile
from dataclasses import dataclass, field

from django.utils.translation import gettext
from rest_framework.exceptions import ValidationError

from .images import MAX_UPLOAD_BYTES
from .photo_names import stem

MAX_FILES = 500
MAX_ZIP_BYTES = 200 * 1024 * 1024
MAX_ZIP_ENTRIES = 2000
MAX_ZIP_UNCOMPRESSED = 600 * 1024 * 1024
MAX_RATIO = 100
MAX_ZIPS_PER_REQUEST = 1
MAX_REQUEST_BYTES = MAX_ZIP_UNCOMPRESSED  # photo bytes one upload request may carry, files and zip together
_IMAGE_EXT = (".jpg", ".jpeg", ".png", ".webp", ".jfif")
_ARCHIVE_EXT = (".zip", ".7z", ".rar", ".tar", ".gz", ".tgz", ".bz2", ".xz")
_ARCHIVE_MAGIC = (b"PK\x03\x04", b"PK\x05\x06", b"7z\xbc\xaf", b"Rar!", b"\x1f\x8b", b"BZh", b"\xfd7zXZ")


@dataclass
class Intake:
    photos: list = field(default_factory=list)  # [(base filename, loader)]; loader() -> bytes, read on demand
    skipped: int = 0
    archives: list = field(default_factory=list)
    total_bytes: int = 0

    def close(self):
        for archive in self.archives:
            archive.close()


def _refuse(message):
    raise ValidationError({"files": message})


def _is_image_name(name):
    return name.lower().endswith(_IMAGE_EXT)


def _add(intake, room, name, loader, size):
    """Count one photo against the batch (placeholders too) and the per-request byte budget."""
    if len(intake.photos) >= room:
        _refuse(gettext("A batch holds at most %(n)d photos.") % {"n": MAX_FILES})
    intake.total_bytes += size
    if intake.total_bytes > MAX_REQUEST_BYTES:
        _refuse(gettext("Too many photos in one upload. Add them in several smaller uploads."))
    intake.photos.append((name, loader))


def _entry_loader(archive, info):
    def load():
        with archive.open(info) as handle:
            data = handle.read(MAX_UPLOAD_BYTES + 1)  # a header that lies about its size is cut off here
        if len(data) > MAX_UPLOAD_BYTES:
            _refuse(gettext("A photo in the zip is too large or suspiciously compressed."))
        if data.startswith(_ARCHIVE_MAGIC):
            _refuse(gettext("Zips inside zips are not accepted."))
        return data
    return load


def _plan_zip(upload, intake, room):
    if getattr(upload, "size", 0) > MAX_ZIP_BYTES:
        _refuse(gettext("A zip can be at most 200 MB. Split it into several."))
    try:
        archive = zipfile.ZipFile(upload)
    except (zipfile.BadZipFile, OSError, ValueError, NotImplementedError):
        _refuse(gettext("That zip could not be read."))
    intake.archives.append(archive)
    infos = archive.infolist()
    if len(infos) > MAX_ZIP_ENTRIES:
        _refuse(gettext("That zip has too many files."))
    if sum(info.file_size for info in infos) > MAX_ZIP_UNCOMPRESSED:
        _refuse(gettext("That zip is too large when unpacked."))
    for info in infos:
        name = info.filename.replace("\\", "/")
        base = name.rsplit("/", 1)[-1]
        if info.is_dir() or name.startswith("__MACOSX/") or base.startswith(".") or not base:
            continue
        if info.flag_bits & 0x1:
            _refuse(gettext("A password-protected zip cannot be used."))
        if base.lower().endswith(_ARCHIVE_EXT):
            _refuse(gettext("Zips inside zips are not accepted."))
        if not _is_image_name(base):
            intake.skipped += 1
            continue
        if info.file_size > MAX_UPLOAD_BYTES or (info.compress_size and info.file_size / info.compress_size > MAX_RATIO):
            _refuse(gettext("A photo in the zip is too large or suspiciously compressed."))
        _add(intake, room, base, _entry_loader(archive, info), info.file_size)


def plan_uploads(uploads, *, existing=0):
    """-> Intake whose photos are read one at a time (M11). Every check that needs no photo bytes runs here,
    before anything is stored: the batch cap (placeholders included), one zip per upload, the per-upload byte
    budget, and every zip guard. The caller reads, stores and drops each photo in turn, then calls `close()`."""
    intake, room = Intake(), MAX_FILES - existing
    try:
        zips = 0
        for upload in uploads:
            name = (getattr(upload, "name", "") or "").replace("\\", "/").rsplit("/", 1)[-1]
            if name.lower().endswith(".zip"):
                zips += 1
                if zips > MAX_ZIPS_PER_REQUEST:
                    _refuse(gettext("Upload one zip at a time."))
                _plan_zip(upload, intake, room)
                continue
            if name.lower().endswith(_ARCHIVE_EXT):
                _refuse(gettext("Upload photos or a .zip of photos."))
            if not _is_image_name(name):
                intake.skipped += 1
                continue
            if upload.size > MAX_UPLOAD_BYTES:
                # over the photo size limit: kept as an empty photo the review lists as unreadable
                _add(intake, room, name, lambda: b"", 0)
                continue
            _add(intake, room, name, lambda upload=upload: upload.read(MAX_UPLOAD_BYTES + 1), upload.size)
        if not intake.photos and not intake.skipped:
            _refuse(gettext("Choose photos or a zip of photos."))
    except Exception:
        intake.close()
        raise
    return intake


def read_uploads(uploads, *, existing=0):
    """`plan_uploads` with every photo read at once: for small inputs only (the guards' tests)."""
    intake = plan_uploads(uploads, existing=existing)
    try:
        intake.photos = [(name, load()) for name, load in intake.photos]
    finally:
        intake.close()
    return intake


def display_name(base):
    """What the review table shows for a file: its base name, bounded."""
    return stem(base)[:200] or "photo"
