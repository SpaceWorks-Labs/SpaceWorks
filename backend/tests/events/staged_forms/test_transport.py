"""Direct model-free checks for chunk revocation, exact sizes and MIME refusal."""
from datetime import UTC, datetime, timedelta
from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))
from apps.makerspaces.private_upload_transport import ObjectLocator, ByteRange, PrivateTransportError, stream_private
from apps.events.staged_forms.file_validation import inspect_file, FileValidationError


class StageTransport(unittest.TestCase):
    def test_reauthorization_after_read_withholds_revoked_bytes(self):
        now = datetime.now(UTC)
        calls = []
        def authorize():
            calls.append("authorize")
            if len(calls) >= 3:
                raise PermissionError("revoked")
        def reader(*args, **kwargs):
            self.assertLessEqual(kwargs["timeout_seconds"], 2)
            return b"x" * kwargs["length"]
        stream = stream_private(locator=ObjectLocator(bucket="private", key="opaque"), byte_range=ByteRange(0, 5, 6, False),
            reader=reader, authorize=authorize, clock=lambda: now, not_after=now + timedelta(seconds=30))
        with self.assertRaises(PermissionError):
            next(stream)

    def test_expired_policy_never_reads_storage(self):
        now = datetime.now(UTC)
        def reader(*args, **kwargs):
            self.fail("Expired stage bytes must not touch storage")
        with self.assertRaises(PrivateTransportError):
            next(stream_private(locator=ObjectLocator(bucket="private", key="opaque"), byte_range=ByteRange(0, 5, 6, False),
                reader=reader, authorize=lambda: None, clock=lambda: now, not_after=now))

    def test_html_executable_wrong_size_and_extension_are_not_file_evidence(self):
        for data, mime, size in ((b"<html>bad</html>", "text/html", 16), (b"MZpayload", "application/pdf", 9),
                                 (b"%PDF", "application/pdf", 20), (b"arbitrary", "image/svg+xml", 9)):
            with self.subTest(mime=mime), self.assertRaises(FileValidationError):
                inspect_file(data, declared_mime=mime, expected_bytes=size)


if __name__ == "__main__":
    unittest.main()
