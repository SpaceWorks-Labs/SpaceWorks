"""A software WebAuthn authenticator for tests: real CBOR, real P-256 signatures."""

import base64
import hashlib
import json
import os
import struct

import cbor2
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.asymmetric import ec

UP, UV, AT = 0x01, 0x04, 0x40


def b64(raw):
    return base64.urlsafe_b64encode(raw).rstrip(b"=").decode()


class SoftAuthenticator:
    def __init__(self, origin="http://localhost:5000", rp_id="localhost"):
        self.origin, self.rp_id = origin, rp_id
        self.key = ec.generate_private_key(ec.SECP256R1())
        self.credential_id = os.urandom(16)
        self.count = 0

    def _cose(self):
        numbers = self.key.public_key().public_numbers()
        return cbor2.dumps({1: 2, 3: -7, -1: 1, -2: numbers.x.to_bytes(32, "big"),
                            -3: numbers.y.to_bytes(32, "big")})

    def _auth_data(self, flags, count, attested=False, rp_id=None):
        data = hashlib.sha256((rp_id or self.rp_id).encode()).digest() + bytes([flags]) + struct.pack(">I", count)
        if attested:
            data += bytes(16) + struct.pack(">H", len(self.credential_id)) + self.credential_id + self._cose()
        return data

    def _client_data(self, kind, challenge, origin=None):
        return json.dumps({"type": kind, "challenge": challenge, "origin": origin or self.origin,
                           "crossOrigin": False}).encode()

    def register(self, options, *, origin=None, uv=True):
        client_data = self._client_data("webauthn.create", options["challenge"], origin)
        auth_data = self._auth_data(UP | AT | (UV if uv else 0), 0, attested=True)
        attestation = cbor2.dumps({"fmt": "none", "attStmt": {}, "authData": auth_data})
        cid = b64(self.credential_id)
        return {"id": cid, "rawId": cid, "type": "public-key", "clientExtensionResults": {},
                "response": {"clientDataJSON": b64(client_data), "attestationObject": b64(attestation),
                             "transports": ["internal"]}}

    def assertion(self, options, *, origin=None, uv=True, count=None, rp_id=None):
        self.count = self.count + 1 if count is None else count
        client_data = self._client_data("webauthn.get", options["challenge"], origin)
        auth_data = self._auth_data(UP | (UV if uv else 0), self.count, rp_id=rp_id)
        signature = self.key.sign(auth_data + hashlib.sha256(client_data).digest(), ec.ECDSA(hashes.SHA256()))
        cid = b64(self.credential_id)
        return {"id": cid, "rawId": cid, "type": "public-key", "clientExtensionResults": {},
                "response": {"clientDataJSON": b64(client_data), "authenticatorData": b64(auth_data),
                             "signature": b64(signature)}}
