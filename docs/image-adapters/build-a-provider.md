---
title: Build an image provider
group: Reference
order: 65
summary: A minimal pseudo-implementation of a background-removal provider, a Python probe to test it, and a conformance checklist.
---

# Build an image provider

A provider is an HTTPS service with two routes. It can be written in any language and run anywhere you can reach
from the SpaceWorks server (the platform setting also accepts a private address such as `http://bg-eraser:8080`;
a space-level setting must be a public `https` address). Changing a saved address needs the shared secret again, in
the same save. SpaceWorks does not ship one: you pick the model and the host.

## Pseudo-implementation

```
state:  SECRET            # the shared secret, at least 16 characters
        seen = Cache(ttl = 600 seconds)          # replay store for nonces

route GET /v1/health:
    check_request(method, path, body = "")
    return 200 json {"status": "ok", "contract": "1", "capabilities": ["image.remove_background"]}

route POST /v1/remove-background:
    body = read_at_most(8 MB + 64 KB)            # bound the read BEFORE trusting the caller
    check_request("POST", request.path, body)    # see below; answers the error itself if it fails
    parts = parse_multipart(body)
    image_bytes, content_type = parts["image"]
    if content_type not in (png, jpeg, webp):    return error(415, "unsupported_media_type")
    if len(image_bytes) > 8 MB:                  return error(413, "payload_too_large")
    image = decode(image_bytes)  or  return error(422, "unreadable_image")
    if max(image.width, image.height) > 4096:    return error(422, "dimensions_too_large")
    cutout = remove_background(image)            # your model: U^2-Net, rembg, a cloud API you trust, ...
    if cutout has no foreground:                 return error(422, "no_subject_found")
    return 200 "image/png" encode_png(cutout)    # RGBA, same proportions as the input

function check_request(method, path, body):
    code = verify(SECRET, method, path, body, request.headers, seen_nonce)   # authentication.md
    if code == "invalid_signature" or code == "stale_timestamp":  respond 401 error(code)
    if code == "replayed_nonce":                                  respond 409 error(code)

function error(status, code):
    return status, json {"error": {"code": code, "message": "...", "retryable": code in (rate_limited, unavailable, internal_error)}}
```

Notes that save debugging time:

- Sign and verify the **path as the client sent it**. Behind a reverse proxy that strips a prefix, verify against the
  original path, not the rewritten one.
- The digest is over the raw body bytes. Do not re-serialise or normalise the multipart body before hashing it.
- Keep the answer's proportions equal to the input. Cropping to the subject is fine for *you* only if you pad back:
  SpaceWorks rejects an answer whose aspect ratio is more than 1% different.
- Do not store the photo or the cut-out after answering, and do not log image bytes or the secret.

## Try your provider

This probe builds the body, signs it exactly as SpaceWorks does and posts it. It needs Python 3 and `requests`
(`pip install requests`). Use `signing.py` from `backend/apps/card_designs/image_adapter/` or copy the `sign` function
from [Authentication](authentication.md).

```python
import hashlib, hmac, secrets, sys, time, requests
from urllib.parse import urlsplit

SECRET, URL, FILE = "your-shared-secret-at-least-16-chars", "https://eraser.example.org", "photo.jpg"

def signed(method, url, **kwargs):
    prepared = requests.Request(method, url, **kwargs).prepare()
    body = prepared.body if isinstance(prepared.body, bytes) else (prepared.body or b"")
    ts, nonce, digest = str(int(time.time())), secrets.token_hex(16), hashlib.sha256(body).hexdigest()
    text = "\n".join(["SW-IMAGE-ADAPTER-V1", method, urlsplit(url).path, ts, nonce, digest]).encode()
    prepared.headers.update({"X-SW-Adapter-Version": "1", "X-SW-Timestamp": ts, "X-SW-Nonce": nonce,
                             "X-SW-Body-SHA256": digest,
                             "X-SW-Signature": "v1=" + hmac.new(SECRET.encode(), text, hashlib.sha256).hexdigest()})
    return requests.Session().send(prepared, timeout=60)

print(signed("GET", URL + "/v1/health").json())
answer = signed("POST", URL + "/v1/remove-background", files={"image": ("photo", open(FILE, "rb"), "image/jpeg")},
                data={"options": '{"output": "png"}'})
print(answer.status_code, answer.headers["Content-Type"])
open("cutout.png", "wb").write(answer.content)
```

## Conformance checklist

Your provider is ready when each of these holds. Then press **Test connection** in SpaceWorks.

1. `/v1/health` answers `contract: "1"` and lists `image.remove_background`.
2. A request with a wrong secret, an altered body, or a different path is `401 invalid_signature`.
3. A timestamp 10 minutes old is `401 stale_timestamp`; the same nonce twice is `409 replayed_nonce`.
4. A GIF is `415`; a 9 MB image is `413`; a 5000 px image is `422 dimensions_too_large`; random bytes are `422 unreadable_image`.
5. A portrait answers `200 image/png` with a transparent background and the same aspect ratio.
6. A photo with no person is `422 no_subject_found`, not an empty PNG.
7. Under load it answers `429` or `503` with a typed body, never a hang longer than 60 s.
8. The secret and the image bytes are not written to logs or disk.

## Licences

Whatever model you choose has its own licence, and so does any weights file you download. SpaceWorks bundles none of
them, so there is nothing to add to the SpaceWorks `NOTICE` file; record the model's licence with your provider.
