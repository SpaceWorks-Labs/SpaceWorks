"""Build-only Noto Sans CJK TrueType instancing (upstream OFL release Sans2.004).

The Debian CJK package has CFF outlines. ReportLab requires glyf outlines:
https://github.com/notofonts/noto-cjk/blob/Sans2.004/Sans/README.md
"""

import hashlib
from io import BytesIO
from urllib.request import urlopen

from fontTools.ttLib import TTFont
from fontTools.varLib.instancer import instantiateVariableFont

from apps.operations.printable_fonts import BUNDLED_FONT_ROOT

REVISION = "523d033d6cb47f4a80c58a35753646f5c3608a78"
BASE = f"https://raw.githubusercontent.com/notofonts/noto-cjk/{REVISION}"
# The commit pin fixes the path; these digests fix the bytes, so a rewritten upstream file fails the build.
SHA256 = {
    "SC": "d68bafcb48a2707749396aa12bbbd833cb70401f3a9a689fd2902c7e0d295964",
    "TC": "ac091cc8cd19e848202afc8fe6d3809b4526c8fdbdb4be82da20c4f785949591",
    "JP": "f4b373b226668ee33a6e54b02823dcd2d1209f17159f777421ae8c2275160369",
    "KR": "9e1d729e7e2b36f9ef439da102f8c134c10aabe46f1c843bf0aca5c043b86f76",
    "LICENSE": "6a73f9541c2de74158c0e7cf6b0a58ef774f5a780bf191f2d7ec9cc53efe2bf2",
}


def _verified(data, name):
    if hashlib.sha256(data).hexdigest() != SHA256[name]:
        raise RuntimeError(f"{name} font download does not match its pinned digest.")
    return data


def bundle():
    BUNDLED_FONT_ROOT.mkdir(parents=True, exist_ok=True)
    for region in ("SC", "TC", "JP", "KR"):
        url = f"{BASE}/Sans/Variable/TTF/Subset/NotoSans{region}-VF.ttf"
        with urlopen(url, timeout=60) as response:
            data = response.read(40 * 1024 * 1024 + 1)
        if len(data) > 40 * 1024 * 1024:
            raise RuntimeError("CJK font download exceeds its bound.")
        _verified(data, region)
        for weight, value in (("Regular", 400), ("Bold", 700)):
            with TTFont(BytesIO(data)) as font:
                if "glyf" not in font:
                    raise RuntimeError("CJK font must have embeddable TrueType outlines.")
                static = instantiateVariableFont(font, {"wght": value}, inplace=True)
                names = {1: f"Noto Sans {region}", 2: weight,
                         4: f"Noto Sans {region} {weight}", 6: f"NotoSans{region}-{weight}"}
                for record in static["name"].names:
                    if record.nameID in names:
                        record.string = names[record.nameID]
                static.save(BUNDLED_FONT_ROOT / f"NotoSans{region}-{weight}.ttf")
    with urlopen(f"{BASE}/LICENSE", timeout=30) as response:
        (BUNDLED_FONT_ROOT / "OFL-Noto-CJK.txt").write_bytes(_verified(response.read(65536), "LICENSE"))


if __name__ == "__main__":
    bundle()
