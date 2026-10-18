"""Check canonical programme bytes against their independently retained metadata."""
from .recipient_selection import BackupBuildError

PROOF_FIELDS = {"expected_size_bytes", "expected_sha256"}


def capture_proof(references):
    proofs = {(row.expected_size_bytes, row.expected_sha256) for row in references
              if row.expected_size_bytes is not None or row.expected_sha256 is not None}
    if len(proofs) > 1:
        raise BackupBuildError("One canonical object has conflicting source byte metadata.")
    if not proofs:
        return {}
    size, digest = proofs.pop()
    return {"expected_size_bytes": size, "expected_sha256": digest}


def assert_capture_proof(expected, captured):
    size, digest = expected.get("expected_size_bytes"), expected.get("expected_sha256")
    if (size is not None and size != captured.get("size")) or (
            digest is not None and digest != captured.get("sha256")):
        raise BackupBuildError("Captured canonical object differs from retained source size/hash.")
