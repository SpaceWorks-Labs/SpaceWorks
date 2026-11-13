"""The deployment image must bundle the fonts required by printable credentials."""

from pathlib import Path
import re
import unittest

from tests.operations.test_report_image_fonts import SHIPPED_TARGETS, stage_chain


class PrintableImageFontsTests(unittest.TestCase):
    # Dockerfile.allinone was removed by 23e4d7c6, leaving backend/Dockerfile as the one
    # runtime image; its shipped targets inherit the font install from `application`.
    def test_runtime_images_install_required_fonts(self):
        root = Path(__file__).resolve().parents[2]
        source = (root / "backend/Dockerfile").read_text(encoding="utf-8")
        for target in SHIPPED_TARGETS:
            with self.subTest(target=target):
                installs = [
                    run for body in stage_chain(source, target)
                    for run in re.findall(r"(?m)^RUN\s+([^\n]+)", body.replace("\\\n", " "))
                ]
                self.assertTrue(any(
                    re.search(r"\bapt-get\s+install\s+[^&;]*\bfonts-noto-core(?=\s|$)", run)
                    for run in installs
                ), f"backend/Dockerfile target {target} must install fonts-noto-core")


if __name__ == "__main__":
    unittest.main()
