import io
import zipfile

from apps.boxes.qr_lookup import label_value
from apps.boxes.qr_render import render_qr_label_svg


def build_batch_zip(batch) -> bytes:
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, mode="w", compression=zipfile.ZIP_DEFLATED) as archive:
        for index, item in enumerate(batch.items.select_related("qr_code"), start=1):
            label = item.label_text
            svg = render_qr_label_svg(label_value(item.qr_code), label)
            archive.writestr(f"{index:02d}-{_sanitize_label(label)}.svg", svg)
    return buffer.getvalue()


def _sanitize_label(label):
    sanitized = "".join(char.lower() if char.isalnum() or char in "-_" else "-" for char in label)
    return sanitized or "qr"
