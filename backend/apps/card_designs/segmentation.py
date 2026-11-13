"""Photo background clean-up on OUR server (Q-I3): never a hosted image API.

A small open-source salient-object model (U^2-Net "u2netp", Apache-2.0, 4.6 MB) runs
through onnxruntime on the CPU. The operator fetches the pinned model once with
`manage.py fetch_card_photo_model`; until then the feature reports itself
unavailable and the clean-up button is hidden. The result is composited on white.
"""
import hashlib
from io import BytesIO
from pathlib import Path

from django.conf import settings

MODEL_URL = "https://github.com/danielgatis/rembg/releases/download/v0.0.0/u2netp.onnx"
MODEL_SHA256 = "309c8469258dda742793dce0ebea8e6dd393174f89934733ecc8b14c76f4ddd8"
SIZE = 320
_session = None


def model_path():
    configured = getattr(settings, "CARD_PHOTO_MODEL_PATH", "")
    if configured:
        return Path(configured)
    import tempfile
    return Path(tempfile.gettempdir()) / "spaceworks-models" / "u2netp.onnx"


def available():
    try:
        import onnxruntime  # noqa: F401
    except Exception:
        return False
    path = model_path()
    return path.is_file() and path.stat().st_size > 1_000_000


def _load():
    global _session
    if _session is None:
        import onnxruntime as ort
        data = model_path().read_bytes()
        if hashlib.sha256(data).hexdigest() != MODEL_SHA256:
            raise RuntimeError("card_photo_model_checksum")
        _session = ort.InferenceSession(data, providers=["CPUExecutionProvider"])
    return _session


def remove_background(image_bytes):
    """-> PNG bytes of the subject on a white background."""
    import numpy as np
    from PIL import Image
    with Image.open(BytesIO(image_bytes)) as opened:
        image = opened.convert("RGB")
    small = np.asarray(image.resize((SIZE, SIZE), Image.LANCZOS), dtype=np.float32) / 255.0
    small = (small - np.array([0.485, 0.456, 0.406], dtype=np.float32)) / np.array([0.229, 0.224, 0.225],
                                                                                    dtype=np.float32)
    batch = small.transpose(2, 0, 1)[None].astype(np.float32)
    session = _load()
    mask = session.run(None, {session.get_inputs()[0].name: batch})[0][0, 0]
    mask = (mask - mask.min()) / max(float(mask.max() - mask.min()), 1e-6)
    alpha = Image.fromarray((mask * 255).astype("uint8"), "L").resize(image.size, Image.LANCZOS)
    white = Image.new("RGB", image.size, (255, 255, 255))
    result = Image.composite(image, white, alpha)
    buffer = BytesIO()
    result.save(buffer, format="PNG", optimize=True)
    return buffer.getvalue()


def fetch_model():
    import httpx
    path = model_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    response = httpx.get(MODEL_URL, follow_redirects=True, timeout=120)
    response.raise_for_status()
    if hashlib.sha256(response.content).hexdigest() != MODEL_SHA256:
        raise RuntimeError("The downloaded model does not match the pinned checksum.")
    path.write_bytes(response.content)
    return path
