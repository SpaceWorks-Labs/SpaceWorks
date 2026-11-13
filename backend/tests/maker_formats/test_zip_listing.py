from io import BytesIO
import struct
import zipfile

import pytest

from apps.maker_formats.errors import FormatError
from apps.maker_formats.range_reader import BytesReader, S3RangeReader
from apps.maker_formats.zip_listing import list_zip
from .samples import archive


@pytest.mark.parametrize("name", ["../x", "/etc/x", "a\\b", "C:x", "\\\\host\\x", "a/../x", "a//x", "a/./x"])
def test_unsafe_paths(name):
    with pytest.raises(FormatError):
        list_zip(BytesReader(archive({name: b"x"})))


def mutate_zip(data, *, flags=None, local_size=None, cd_size=None, offset=None, attrs=None):
    result = bytearray(data)
    cd = result.index(b"PK\x01\x02")
    if flags is not None:
        struct.pack_into("<H", result, 6, flags)
        struct.pack_into("<H", result, cd + 8, flags)
    if local_size is not None:
        struct.pack_into("<I", result, 22, local_size)
    if cd_size is not None:
        struct.pack_into("<I", result, cd + 24, cd_size)
    if offset is not None:
        struct.pack_into("<I", result, cd + 42, offset)
    if attrs is not None:
        struct.pack_into("<I", result, cd + 38, attrs)
    return bytes(result)


@pytest.mark.parametrize("kw", [{"flags": 1}, {"local_size": 9}, {"cd_size": 9}, {"offset": 1},
                                 {"attrs": 0o120777 << 16}, {"offset": 0xffffffff}])
def test_encryption_symlink_lies_and_zip64(kw):
    with pytest.raises(FormatError):
        list_zip(BytesReader(mutate_zip(archive({"a.txt": b"x"}), **kw)))


def test_entry_and_directory_limits_duplicates_and_ratio():
    with pytest.raises(FormatError):
        list_zip(BytesReader(archive({str(i): b"a" for i in range(2001)})))
    with pytest.raises(FormatError):
        list_zip(BytesReader(archive({("x" * 1000) + str(i): b"a" for i in range(1100)})))
    with pytest.raises(FormatError):
        list_zip(BytesReader(archive({"a.txt": b"a", "A.txt": b"b"})))
    output = BytesIO()
    with zipfile.ZipFile(output, "w", zipfile.ZIP_DEFLATED) as handle:
        handle.writestr("bomb", b"0" * 1000000)
    with pytest.raises(FormatError):
        list_zip(BytesReader(output.getvalue()))


def test_appended_polyglot_and_corrupt_end_record_rejected():
    valid = archive({"a.txt": b"a"})
    for bad in (b"\x89PNG\r\n" + valid, valid + b"trailing", valid[:-1]):
        with pytest.raises(FormatError):
            list_zip(BytesReader(bad))


def test_valid_data_descriptor_and_nested_flag_without_entry_open(monkeypatch):
    class Unseekable(BytesIO):
        def seekable(self):
            return False
        def seek(self, *args):
            raise OSError()
    output = Unseekable()
    with zipfile.ZipFile(output, "w", zipfile.ZIP_STORED) as handle:
        handle.writestr("nested.zip", b"nested content listed, not opened")
    monkeypatch.setattr(zipfile.ZipFile, "open", lambda *a, **k: pytest.fail("entry extraction"))
    entries = list_zip(BytesReader(output.getvalue()))
    assert entries[0].nested_archive is True


def test_s3_range_listing_never_reads_large_payload_or_extracts():
    data = archive({"large.bin": b"x" * (2 * 1024 ** 2)})
    calls = []
    class Client:
        def get_object(self, **kwargs):
            assert kwargs["VersionId"] == "frozen-version"
            left, right = map(int, kwargs["Range"].removeprefix("bytes=").split("-"))
            calls.append((left, right))
            assert right - left < 1024 ** 2
            assert not (left < 100 and right > 1000)
            block = data[left:right+1]
            return {"ContentRange": f"bytes {left}-{right}/{len(data)}", "ContentLength": len(block), "Body": BytesIO(block)}
    reader = S3RangeReader(Client(), bucket="private", key="verification/owned", size=len(data), version_id="frozen-version")
    assert list_zip(reader)[0].name == "large.bin"
    assert sum(r-l+1 for l,r in calls) < 1000


def test_range_ignored_by_storage_fails_closed():
    class Client:
        def get_object(self, **kwargs):
            return {"Body": BytesIO(b"full payload"), "ContentLength": 12}
    reader = S3RangeReader(Client(), bucket="x", key="owned", size=12, etag="frozen")
    with pytest.raises(FormatError, match="invalid_storage_range"):
        reader.read(0, 4)
