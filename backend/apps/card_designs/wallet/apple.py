"""Build and sign an Apple Wallet .pkpass (generic style).

A pkpass is a ZIP of pass.json, images, manifest.json (SHA-1 of every file) and a
detached PKCS#7 signature of the manifest made with the Pass Type ID certificate and Apple's
WWDR intermediate. Credentials are resolved per makerspace (`credentials.apple_for`): the
space's own, else the platform's. Holder-card passes carry a web-service URL so they update
after an APNs push (`views_apple.py`, `apple_push.py`); guest passes are STATIC: they carry
an expiry and no web service, and depend on server-side token revocation (`guest.py`).
"""
import hashlib
import io
import json
import zipfile

from django.conf import settings

from .credentials import auth_token


def _rgb(value):
    value = value.lstrip("#")
    return "rgb({}, {}, {})".format(*(int(value[i:i + 2], 16) for i in (0, 2, 4)))


def _icon(size):
    """The Space Works symbol on cream, rasterised through the same pdfium path as cards."""
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


def _logo(makerspace, scale):
    """The space's own logo scaled into Apple's 160x50 pt logo box, else the Space Works symbol."""
    from ..images import read_public_image
    try:
        data = read_public_image(getattr(makerspace, "logo_key", "")) if makerspace is not None else None
        if data:
            from PIL import Image
            image = Image.open(io.BytesIO(data)).convert("RGBA")
            image.thumbnail((160 * scale, 50 * scale))
            out = io.BytesIO()
            image.save(out, "PNG")
            return out.getvalue()
    except Exception:  # a broken logo never blocks a pass
        pass
    return _icon(50 * scale)


def pass_json(creds, serial, content, *, wallet_pass=None):
    """pass.json bytes. `wallet_pass` adds the update web service; without it the pass is static."""
    body = {
        "formatVersion": 1, "passTypeIdentifier": creds.pass_type_id, "teamIdentifier": creds.team_id,
        "serialNumber": serial, "organizationName": content["issuer"][:64],
        "description": f"{content['issuer']} {content.get('description', 'card')}"[:120],
        "backgroundColor": _rgb("#006E63"), "foregroundColor": _rgb("#FFF4E8"), "labelColor": _rgb("#DFFF8F"),
        "generic": {
            "primaryFields": [{"key": "name", "label": "Name", "value": content["name"]}],
            "secondaryFields": [{"key": "number", "label": "Number", "value": content["number"]},
                                {"key": "valid", "label": "Valid until", "value": content["valid_until"]}],
            "auxiliaryFields": [{"key": "label", "label": content["label"], "value": content["label_value"]}],
        },
    }
    if wallet_pass is not None:
        base = (getattr(settings, "PUBLIC_API_BASE_URL", "") or getattr(settings, "PUBLIC_APP_BASE_URL", "")).rstrip("/")
        body["authenticationToken"] = auth_token(serial)
        body["webServiceURL"] = f"{base}/api/v1/wallet/apple"
    if content.get("expires_at"):
        body["expirationDate"] = content["expires_at"]
    elif content["standing"] == "expired":
        # Decision 253(c): an expired pass shows as expired (a past expirationDate), never as voided.
        from django.utils import timezone
        body["expirationDate"] = timezone.now().strftime("%Y-%m-%dT%H:%M:%SZ")
    if content["qr"]:
        body["barcodes"] = [{"format": "PKBarcodeFormatQR", "message": content["qr"], "messageEncoding": "iso-8859-1"}]
    if content["standing"] == "revoked" or (wallet_pass is not None and wallet_pass.voided_at):
        body["voided"] = True
    return json.dumps(body, separators=(",", ":")).encode()


def _sign(manifest, creds):
    from cryptography.hazmat.primitives import hashes, serialization
    from cryptography.hazmat.primitives.serialization import pkcs7
    cert, key, wwdr = creds.material()
    return (pkcs7.PKCS7SignatureBuilder().set_data(manifest).add_signer(cert, key, hashes.SHA256())
            .add_certificate(wwdr)
            .sign(serialization.Encoding.DER, [pkcs7.PKCS7Options.DetachedSignature, pkcs7.PKCS7Options.Binary]))


def build_pkpass_bytes(creds, serial, content, *, makerspace=None, wallet_pass=None):
    files = {"pass.json": pass_json(creds, serial, content, wallet_pass=wallet_pass),
             "icon.png": _icon(29), "icon@2x.png": _icon(58), "logo.png": _logo(makerspace, 1),
             "logo@2x.png": _logo(makerspace, 2)}
    manifest = json.dumps({name: hashlib.sha1(data).hexdigest() for name, data in files.items()},
                          separators=(",", ":")).encode()
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w", zipfile.ZIP_DEFLATED) as archive:
        for name, data in files.items():
            archive.writestr(name, data)
        archive.writestr("manifest.json", manifest)
        archive.writestr("signature", _sign(manifest, creds))
    return buffer.getvalue()


def build_pkpass(wallet_pass, content):
    """The holder-card pass (updatable); signed with the space's, else the platform's, credentials."""
    from .credentials import apple_for
    creds = apple_for(wallet_pass.makerspace_id)
    if creds is None:
        raise LookupError("apple wallet credentials are not configured")
    return build_pkpass_bytes(creds, wallet_pass.serial, content, makerspace=wallet_pass.makerspace,
                              wallet_pass=wallet_pass)
