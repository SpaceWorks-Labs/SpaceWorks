"""Designer-preview stand-ins: a head-and-shoulders silhouette PNG with alpha, drawn procedurally (no asset to license)."""
from functools import lru_cache
from io import BytesIO


@lru_cache(maxsize=1)
def silhouette_png():
    """A 600 x 800 cut-out-style portrait (alpha PNG): the preview of a `cutout` photo variant with the sticker outline."""
    from PIL import Image, ImageDraw
    scale = 2
    image = Image.new("RGBA", (600 * scale, 800 * scale), (0, 0, 0, 0))
    draw = ImageDraw.Draw(image)
    ink = (61, 92, 88, 255)
    draw.ellipse([190 * scale, 80 * scale, 410 * scale, 330 * scale], fill=ink)  # head
    draw.rounded_rectangle([265 * scale, 300 * scale, 335 * scale, 400 * scale], radius=20 * scale, fill=ink)  # neck
    draw.pieslice([40 * scale, 360 * scale, 560 * scale, 960 * scale], 180, 360, fill=ink)  # shoulders
    draw.rectangle([40 * scale, 660 * scale, 560 * scale, 800 * scale], fill=ink)
    buffer = BytesIO()
    image.resize((600, 800), Image.LANCZOS).save(buffer, format="PNG")
    return buffer.getvalue()


def wants_cutout(document):
    from .layout import sides
    return any(layer["kind"] == "photo" and layer.get("variant", "original") != "original"
               for side in sides(document) for layer in document[side]["layers"])
