"""Rasterize only checksum-pinned packaged vectors, never uploaded SVG or URLs.

The twelve ARTWORK assets use rectangles and straight M/L/H/V/Z paths. Keeping
that closed vocabulary avoids an SVG engine with network/font/resource access.
"""

from hashlib import sha256
from io import BytesIO
from pathlib import Path
import re
from xml.etree import ElementTree

from PIL import Image, ImageDraw
from rest_framework.exceptions import ValidationError

from apps.events.default_templates.manifest import ARTWORK, artwork_resource

ROOT = Path(__file__).resolve().parents[1] / "default_templates"
TOKEN = re.compile(r"[MLHVZ]|-?(?:\d+(?:\.\d*)?|\.\d+)")


def packaged_resource(resource_id):
    for item in ARTWORK:
        resource = artwork_resource(item["template_id"], item["theme"])
        if resource["id"] == str(resource_id):
            return resource
    raise ValidationError({"resource_id": "Choose a packaged artwork resource."})


def _paths(value):
    tokens = TOKEN.findall(value)
    if re.sub(r"[\s,]", "", value) != "".join(tokens):
        raise ValueError("Unsupported packaged SVG path.")
    paths, points, command, index = [], [], None, 0
    x = y = 0.0
    while index < len(tokens):
        if tokens[index] in {"M", "L", "H", "V", "Z"}:
            command = tokens[index]
            index += 1
            if command == "Z":
                paths.append((points, True))
                x, y = points[0]
                points, command = [], None
                continue
            if command == "M" and points:
                paths.append((points, False))
                points = []
        if command in ("M", "L"):
            x, y = float(tokens[index]), float(tokens[index+1])
            index += 2
        elif command == "H":
            x, index = float(tokens[index]), index+1
        elif command == "V":
            y, index = float(tokens[index]), index+1
        else:
            raise ValueError("Invalid packaged SVG path.")
        points.append((x, y))
        if command == "M":
            command = "L"
    if points:
        paths.append((points, False))
    return paths


def render_packaged(resource_id, *, width_mm, height_mm):
    resource = packaged_resource(resource_id)
    content = (ROOT / resource["path"]).read_bytes()
    if sha256(content).hexdigest() != resource["sha256"]:
        raise ValidationError({"resource_id": "Packaged artwork checksum changed."})
    root = ElementTree.fromstring(content)
    left, top, width, height = map(float, root.attrib["viewBox"].split())
    size = (round(width_mm * 300 / 25.4), round(height_mm * 300 / 25.4))
    if min(size) < 1 or size[0]*size[1] > 16_000_000:
        raise ValidationError({"resource_id": "Artwork dimensions exceed the print limit."})
    sx, sy = size[0]/width, size[1]/height
    with Image.new("RGBA", size) as image:
        draw = ImageDraw.Draw(image)
        def scale(point):
            return ((point[0]-left)*sx, (point[1]-top)*sy)
        for child in root:
            tag, a = child.tag.rsplit("}", 1)[-1], child.attrib
            fill = a.get("fill", "none")
            fill = None if fill == "none" else fill
            stroke = a.get("stroke")
            pen = max(1, round(float(a.get("stroke-width", 1))*min(sx, sy)))
            if tag == "rect" and not float(a.get("rx", 0)):
                x, y, w, h = (float(a.get(key, 0)) for key in ("x", "y", "width", "height"))
                draw.rectangle((scale((x, y)), scale((x+w, y+h))), fill=fill, outline=stroke, width=pen)
            elif tag == "path":
                for points, closed in _paths(a["d"]):
                    pixels = list(map(scale, points))
                    if fill:
                        draw.polygon(pixels, fill=fill)
                    if stroke:
                        draw.line(pixels+pixels[:1] if closed else pixels, fill=stroke, width=pen, joint="curve")
            else:
                raise ValueError("Unsupported packaged SVG element.")
        output = BytesIO()
        image.save(output, format="PNG")
        return output.getvalue()
