"""Model-free scanner protocol, sanitized failures and size/type fail-closed tests."""
import importlib.util
import struct
import unittest
from apps.payments.event_payouts.attachment_content import ContentError, scan, validate


class Socket:
    def __init__(self, response):
        self.response, self.sent = response, []
    def __enter__(self):
        return self
    def __exit__(self, *args):
        pass
    def settimeout(self, timeout):
        assert timeout == 2
    def sendall(self, data):
        self.sent.append(data)
    def recv(self, size):
        result, self.response = self.response[:size], self.response[size:]
        return result


class ScannerPolicy(unittest.TestCase):
    def test_disabled_scanner_records_explicit_policy(self):
        result = scan(b"private receipt", backend="none")
        self.assertEqual((result.status, result.version), ("skipped", "policy-none-v1"))

    def test_configured_scanner_never_falls_back_to_skip(self):
        def unavailable(*args, **kwargs):
            raise OSError("private routing data must not be echoed")
        for options in ({"host": None}, {"host": "scanner", "connect": unavailable}):
            with self.assertRaises(ContentError) as caught:
                scan(b"private", backend="clamav", **options)
            self.assertEqual((caught.exception.code, caught.exception.status), ("scanner_unavailable", 503))
            self.assertNotIn("private", str(caught.exception))

    def test_clamav_uses_bounded_instream_and_clean_version(self):
        version, upload = Socket(b"ClamAV 1.4.2/123456/Tue\0"), Socket(b"stream: OK\0")
        sockets = iter((version, upload))
        result = scan(b"abcd", backend="clamav", host="clam", connect=lambda *a, **kw: next(sockets))
        self.assertEqual((result.status, result.version), ("clean", "1.4.2/123456"))
        self.assertEqual(b"".join(upload.sent), b"zINSTREAM\0" + struct.pack("!I", 4) + b"abcd\0\0\0\0")

    def test_infected_incomplete_or_unknown_responses_refuse_readiness(self):
        for reply in (b"stream: signature FOUND\0", b"stream: ERROR\0", b"broken"):
            sockets = iter((Socket(b"ClamAV 1.4.2/123456/Tue\0"), Socket(reply)))
            if b"FOUND" in reply:
                self.assertEqual(scan(b"abcd", backend="clamav", host="clam", connect=lambda *a, **kw: next(sockets)).status, "infected")
            else:
                with self.assertRaises(ContentError):
                    scan(b"abcd", backend="clamav", host="clam", connect=lambda *a, **kw: next(sockets))

    def test_empty_and_oversized_objects_rejected_before_decoder(self):
        for data in (b"", b"a" * (10485760 + 1)):
            with self.assertRaises(ContentError) as caught:
                validate(data, declared_mime="image/png", purpose="reimbursement_receipt")
            self.assertEqual(caught.exception.status, 413)


if __name__ == "__main__":
    unittest.main()
