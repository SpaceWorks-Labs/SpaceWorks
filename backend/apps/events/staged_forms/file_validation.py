"""Bounded document decoding; MIME/filename alone never admit an upload."""
import hashlib
from io import BytesIO
import warnings

MIMES = frozenset({"application/pdf", "image/jpeg", "image/png", "image/heic"})
MAX_BYTES = 10 * 1024 * 1024


class FileValidationError(ValueError):
    def __init__(self, code):
        self.code = code
        super().__init__(code)


def inspect_file(data, *, declared_mime, expected_bytes):
    if not isinstance(data, bytes) or not 0 < len(data) == expected_bytes <= MAX_BYTES:
        raise FileValidationError("stage_file_size_mismatch")
    if declared_mime not in MIMES:
        raise FileValidationError("stage_file_type_unsupported")
    if declared_mime == "application/pdf":
        if not data.startswith(b"%PDF-") or b"%%EOF" not in data[-4096:]:
            raise FileValidationError("stage_file_invalid")
        try:
            from pypdf import PdfReader
            reader = PdfReader(BytesIO(data), strict=True)
            count = reader.trailer["/Root"]["/Pages"].get("/Count")
            if not isinstance(count, int) or not 0 < count <= 2000:
                raise FileValidationError("stage_file_invalid")
            if reader.is_encrypted or not 0 < len(reader.pages) <= 2000:
                raise FileValidationError("stage_file_invalid")
        except ImportError as exc:
            raise FileValidationError("stage_decoder_unavailable") from exc
        except FileValidationError:
            raise
        except Exception as exc:
            raise FileValidationError("stage_file_invalid") from exc
    else:
        try:
            from PIL import Image
            if declared_mime == "image/heic":
                from pillow_heif import register_heif_opener
                register_heif_opener()
            with warnings.catch_warnings():
                warnings.simplefilter("error", Image.DecompressionBombWarning)
                with Image.open(BytesIO(data)) as image:
                    width, height = image.size
                    expected = {"image/jpeg": {"JPEG"}, "image/png": {"PNG"}, "image/heic": {"HEIF", "HEIC"}}
                    if (image.format not in expected[declared_mime] or not 0 < width <= 16000
                            or not 0 < height <= 16000 or width * height > 40_000_000
                            or getattr(image, "n_frames", 1) != 1):
                        raise FileValidationError("stage_file_invalid")
                    image.load()
        except ImportError as exc:
            raise FileValidationError("stage_decoder_unavailable") from exc
        except FileValidationError:
            raise
        except Exception as exc:
            raise FileValidationError("stage_file_invalid") from exc
    return {"sha256": hashlib.sha256(data).hexdigest(), "canonical_mime": declared_mime, "actual_bytes": len(data)}
