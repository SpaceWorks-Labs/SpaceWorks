"""Build and sign an Apple Wallet .pkpass (generic style) for one holder card.

A pkpass is a ZIP of pass.json, images, manifest.json (SHA-1 of every file) and a
detached PKCS#7 signature of the manifest made with the platform Pass Type ID
certificate and Apple's WWDR intermediate. Updates arrive through the pass web
service (`views_apple.py`) after an APNs push (`apple_push.py`).
"""
import hashlib
import io
import json
import zipfile

from django.conf import settings

from .credentials import apple_material, auth_token


def _rgb(value):
    value = value.lstrip("#")
    return "rgb({}, {}, {})".format(*(int(value[i:i + 2], 16) for i in (0, 2, 4)))


def _icon(size):
    """The Space Works symbol on teal, rasterised through the same pdfium path as cards."""
    from reportlab.pdfgen.canvas import Canvas
    from ..raster import pdf_page_to_png
    from ..symbol import draw_symbol
    buffer = io.BytesIO()
    canvas = Canvas(buffer, pagesize=(size, size))
    canvas.setFillColorRGB(1, 0.957, 0.91)
    canvas.rect(0, 0, size, size, fill=1, stroke=0)
    draw_symbol(canvas, size * 0.12, size * 0.12, size * 0.76, size * 0.76)
    canvas.showPage()
    canvas.save()
    return pdf_page_to_png(buffer.getvalue(), dpi=72)


def pass_json(wallet_pass, content):
    base = (getattr(settings, "PUBLIC_API_BASE_URL", "") or getattr(settings, "PUBLIC_APP_BASE_URL", "")).rstrip("/")
    body = {
        "formatVersion": 1, "passTypeIdentifier": settings.WALLET_APPLE_PASS_TYPE_ID,
        "teamIdentifier": settings.WALLET_APPLE_TEAM_ID, "serialNumber": wallet_pass.serial,
        "authenticationToken": auth_token(wallet_pass.serial), "webServiceURL": f"{base}/api/v1/wallet/apple",
        "organizationName": content["issuer"][:64], "description": f"{content['issuer']} card"[:120],
        "backgroundColor": _rgb("#006E63"), "foregroundColor": _rgb("#FFF4E8"), "labelColor": _rgb("#DFFF8F"),
        "generic": {
            "primaryFields": [{"key": "name", "label": "Name", "value": content["name"]}],
            "secondaryFields": [{"key": "number", "label": "Number", "value": content["number"]},
                                {"key": "valid", "label": "Valid until", "value": content["valid_until"]}],
            "auxiliaryFields": [{"key": "label", "label": content["label"], "value": content["label_value"]}],
        },
    }
    if content["qr"]:
        body["barcodes"] = [{"format": "PKBarcodeFormatQR", "message": content["qr"], "messageEncoding": "iso-8859-1"}]
    if content["standing"] != "valid" or wallet_pass.voided_at:
        body["voided"] = True
    return json.dumps(body, separators=(",", ":")).encode()


def _sign(manifest):
    from cryptography.hazmat.primitives import hashes, serialization
    from cryptography.hazmat.primitives.serialization import pkcs7
    cert, key, wwdr = apple_material()
    return (pkcs7.PKCS7SignatureBuilder().set_data(manifest).add_signer(cert, key, hashes.SHA256())
            .add_certificate(wwdr)
            .sign(serialization.Encoding.DER, [pkcs7.PKCS7Options.DetachedSignature, pkcs7.PKCS7Options.Binary]))


def build_pkpass(wallet_pass, content):
    files = {"pass.json": pass_json(wallet_pass, content), "icon.png": _icon(29), "icon@2x.png": _icon(58),
             "logo.png": _icon(50)}
    manifest = json.dumps({name: hashlib.sha1(data).hexdigest() for name, data in files.items()},
                          separators=(",", ":")).encode()
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w", zipfile.ZIP_DEFLATED) as archive:
        for name, data in files.items():
            archive.writestr(name, data)
        archive.writestr("manifest.json", manifest)
        archive.writestr("signature", _sign(manifest))
    return buffer.getvalue()
