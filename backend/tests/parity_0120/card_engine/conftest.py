"""Card Studio (decisions 314/315) fixtures: the test host counts as a platform host; storage is an in-memory dict."""
from io import BytesIO
from uuid import uuid4

import pytest


@pytest.fixture(autouse=True)
def card_test_host(settings):
    settings.INFRA_HOSTS = {*settings.INFRA_HOSTS, "testserver"}


def png(size=(60, 80), colour=(180, 40, 40, 255)):
    from PIL import Image
    out = BytesIO()
    Image.new("RGBA", size, colour).save(out, format="PNG")
    return out.getvalue()


def silhouette(size=(60, 80)):
    """A cut-out-style PNG: an opaque block in the middle, transparent border (the alpha edge the outline follows)."""
    from PIL import Image
    image = Image.new("RGBA", size, (0, 0, 0, 0))
    image.paste((20, 20, 200, 255), (size[0] // 4, size[1] // 4, size[0] * 3 // 4, size[1] * 3 // 4))
    out = BytesIO()
    image.save(out, format="PNG")
    return out.getvalue()


def uid():
    return str(uuid4())


def layer(kind, x, y, w, h, **extra):
    return {"id": uid(), "kind": kind, "name": kind, "x_mm": x, "y_mm": y, "w_mm": w, "h_mm": h, **extra}


def document(layers, *, stock="cr80-portrait", background=None, **top):
    return {"version": 3, "stock": stock, "back_enabled": False, "mono": False,
            "front": {"background": background or {"kind": "colour", "colour": "#FFFFFF"}, "layers": layers},
            "back": {"layers": []}, **top}


@pytest.fixture
def store(monkeypatch):
    """In-memory private storage for design assets (put and read) used by template import/export."""
    objects = {}
    from apps.card_designs import templates_files

    def put(key, data, content_type):
        objects[key] = data
        return len(data)

    monkeypatch.setattr(templates_files, "put_bytes", put)
    monkeypatch.setattr(templates_files, "read_optional", lambda key, limit=0: objects.get(key))
    return objects
