"""What SpaceWorks accepts back from a provider: a decodable PNG with a real alpha channel.

The answer is decoded and re-encoded (so provider metadata never reaches storage), must be no larger than the
contract's edge limit, must keep the input's aspect ratio (within 1%), and must neither be fully opaque (nothing
was removed) nor fully transparent (nothing was kept). A `{mask_url}` answer is turned into the same RGBA here.

The size is checked from the image header, right after `Image.open` and BEFORE anything is decoded or converted
(security review L-C1): a small, highly compressed PNG that claims 10000 x 10000 is refused without allocating
its pixels. Pillow's own decompression-bomb guard stays on as a second line.
"""
from io import BytesIO

from .contract import MAX_INPUT_EDGE, MAX_OUTPUT_BYTES
from .errors import AdapterError

ASPECT_TOLERANCE = 0.01
MAX_PIXELS = MAX_INPUT_EDGE * MAX_INPUT_EDGE


def _open(data, code, size_code="response_shape_mismatch"):
    from PIL import Image, UnidentifiedImageError
    try:
        image = Image.open(BytesIO(data))  # reads the header only
    except (UnidentifiedImageError, OSError, ValueError, Image.DecompressionBombError):
        raise AdapterError(code) from None
    width, height = image.size
    if max(width, height) > MAX_INPUT_EDGE or min(width, height) < 1 or width * height > MAX_PIXELS:
        image.close()
        raise AdapterError(size_code)
    try:
        image.load()
    except (OSError, ValueError, Image.DecompressionBombError):
        raise AdapterError(code) from None
    return image


def _check_shape(image, source_size):
    if max(image.size) > MAX_INPUT_EDGE or min(image.size) < 1:
        raise AdapterError("response_shape_mismatch")
    ratio_out, ratio_in = image.width / image.height, source_size[0] / source_size[1]
    if abs(ratio_out - ratio_in) / ratio_in > ASPECT_TOLERANCE:
        raise AdapterError("response_shape_mismatch")


def _encode(image):
    out = BytesIO()
    image.save(out, format="PNG", optimize=True)
    data = out.getvalue()
    if len(data) > MAX_OUTPUT_BYTES:
        raise AdapterError("response_too_large")
    return data


def _check_alpha(alpha):
    low, high = alpha.getextrema()
    if low == 255:
        raise AdapterError("response_no_alpha")
    if high == 0:
        raise AdapterError("response_empty")


def validate_png(data, source_size):
    """-> (png_bytes, width, height). Raises AdapterError with a typed code."""
    if not data or len(data) > MAX_OUTPUT_BYTES:
        raise AdapterError("response_too_large" if data else "response_empty")
    image = _open(data, "response_not_png")
    if image.format != "PNG":
        raise AdapterError("response_not_png")
    if image.mode not in ("RGBA", "LA", "PA") and "transparency" not in image.info:
        raise AdapterError("response_no_alpha")
    image = image.convert("RGBA")
    _check_shape(image, source_size)
    _check_alpha(image.getchannel("A"))
    return _encode(image), image.width, image.height


def apply_mask(original, mask_data, source_size):
    """The provider answered with a grayscale mask instead of a cut-out: apply it to the original photo."""
    mask = _open(mask_data, "response_not_png").convert("L")
    _check_shape(mask, source_size)
    base = _open(original, "input_not_allowed", "input_not_allowed").convert("RGBA")
    if mask.size != base.size:
        from PIL import Image
        mask = mask.resize(base.size, Image.LANCZOS)
    _check_alpha(mask)
    base.putalpha(mask)
    return _encode(base), base.width, base.height
