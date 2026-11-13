"""Report font packaging contracts; runnable directly without Django or Docker."""

from pathlib import Path
import re
import shlex
import unittest


ROOT = Path(__file__).resolve().parents[3]
# The published image (`release`) and the default source-build target (`full`) both ship.
SHIPPED_TARGETS = ("release", "full")


def stage_chain(dockerfile, target):
    """Return the bodies of `target` and every stage it inherits FROM, nearest first.

    A font installed in a stage outside this chain (a frontend builder, say) never ships.
    """
    stages, parents = {}, {}
    for match in re.finditer(r"(?im)^FROM\s+(\S+)(?:\s+AS\s+(\S+))?[^\n]*\n(.*?)(?=^FROM\s|\Z)", dockerfile, re.S | re.M):
        name = (match.group(2) or "").lower()
        stages[name], parents[name] = match.group(3), match.group(1).lower()
    assert target in stages, f"stage {target} is missing"
    chain, name = [], target
    while name in stages:
        chain.append(stages[name])
        name = parents[name]
    return chain


class ReportImageFontTests(unittest.TestCase):
    def assert_runtime_installs_unicode_font(self, filename, target):
        dockerfile = (ROOT / filename).read_text(encoding="utf-8")
        packages = set()
        for body in stage_chain(dockerfile, target):
            for instruction in body.replace("\\\n", " ").splitlines():
                if not instruction.startswith("RUN "):
                    continue
                # The shared base stage installs inside one `set -eux; ... ;` shell script, so
                # split on `;` as well as `&&` and accept a leading `then`/`do`/`else`.
                for command in re.split(r"&&|;|\|\|", instruction[4:]):
                    tokens = shlex.split(command)
                    while tokens and tokens[0] in {"then", "do", "else"}:
                        tokens = tokens[1:]
                    if tokens[:2] == ["apt-get", "install"]:
                        packages.update(tokens[2:])
        self.assertIn("fonts-dejavu-core", packages, f"{filename} target {target}")

    # The all-in-one image (Dockerfile.allinone) was dropped in 23e4d7c6; the backend
    # image is the only runtime that renders report images. Since the cloud programme
    # (08ed1e57) it is multi-stage: the fonts live in the shared `application` base that
    # every shipped target inherits, so the whole inheritance chain is inspected.
    def test_backend_runtime_installs_unicode_font(self):
        for target in SHIPPED_TARGETS:
            with self.subTest(target=target):
                self.assert_runtime_installs_unicode_font("backend/Dockerfile", target)


if __name__ == "__main__":
    unittest.main()
