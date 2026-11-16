"""Run the conformance checks against a live server by URL.

    python -I -m tests.adapter_conformance.run --url https://dev.example --device <uuid> --key-version 1 \
        --private-key <base64 raw Ed25519 seed> --binding <uuid> [--expect-command]

Run it from the ``backend/`` directory (so ``apps.devices.protocol`` and ``apps.ed25519`` import). The exit code
is 0 only when every check passes.
"""
import argparse
import base64
import sys

from tests.adapter_conformance.client import AdapterClient, UrlTransport
from tests.adapter_conformance.conformance import report, run
from tests.adapter_conformance.rails import run_rails


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--url", required=True)
    parser.add_argument("--device", required=True)
    parser.add_argument("--key-version", type=int, default=1)
    parser.add_argument("--private-key", required=True, help="base64 of the raw 32-byte Ed25519 private key")
    parser.add_argument("--binding", required=True)
    parser.add_argument("--expect-command", action="store_true",
                        help="a staff user has queued a control command; also check lease and ack")
    args = parser.parse_args(argv)
    client = AdapterClient(UrlTransport(args.url), args.device, args.key_version, base64.b64decode(args.private_key))
    results = run(client, args.binding, expect_command=args.expect_command) + run_rails(client, args.binding)
    return 0 if report(results) else 1


if __name__ == "__main__":
    sys.exit(main())
