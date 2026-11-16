"""Shared builders for the certificate-on-the-shared-engine tests (decision 315)."""
from io import BytesIO
from uuid import uuid4

PNG_SIZE = (60, 80)


def png(size=PNG_SIZE, colour=(180, 40, 40, 255)):
    from PIL import Image
    out = BytesIO()
    Image.new("RGBA", size, colour).save(out, format="PNG")
    return out.getvalue()


def uid():
    return str(uuid4())


def layer(kind, x, y, w, h, **extra):
    return {"id": uid(), "kind": kind, "name": kind, "x_mm": x, "y_mm": y, "w_mm": w, "h_mm": h, **extra}


def certificate(layers, *, stock="a4-landscape", **top):
    """A minimal `kind: certificate` document (version 3), white paper, single page."""
    return {"version": 3, "kind": "certificate", "stock": stock, "back_enabled": False, "mono": False,
            "front": {"background": {"kind": "colour", "colour": "#FFFFFF"}, "layers": layers},
            "back": {"layers": []}, **top}


def signature(slot=1, x=20, y=120, w=70, h=30, **extra):
    return layer("signature", x, y, w, h, signatory_slot=slot, **extra)


def signatory(name="Dr Director", title="Director", *, image=True, approved=True):
    return {"name": name, "title": title, "image": png() if image else None, "approved": approved}
