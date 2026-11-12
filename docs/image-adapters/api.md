---
title: Image Adapter API: requests, responses, limits
group: Reference
order: 62
summary: Exactly what SpaceWorks sends to a background-removal provider and what the provider must answer.
---

# Requests, responses and limits

All paths are relative to the **provider address** you enter in settings (for example `https://eraser.example.org`).
If the address has a path prefix (`https://example.org/eraser`), the prefix is part of the signed path.

## `POST /v1/remove-background`

**Request**: `multipart/form-data`

| Part | Required | Meaning |
|---|---|---|
| `image` | yes | The photo, with its own `Content-Type`: `image/png`, `image/jpeg` or `image/webp`. |
| `options` | no | JSON text. v1 sends `{"output": "png"}`. Ignore unknown keys. |

**Headers** (see [Authentication](authentication.md)):
`X-SW-Adapter-Version: 1`, `X-SW-Timestamp`, `X-SW-Nonce`, `X-SW-Body-SHA256`, `X-SW-Signature`.

**Answer, success (HTTP 200), one of:**

1. `Content-Type: image/png`: a PNG **with an alpha channel**: the person opaque, the background transparent.
2. `Content-Type: application/json`: `{"mask_url": "https://..."}`: a public `https` URL of a grayscale PNG mask
   (white = keep). SpaceWorks fetches it (max 8 MB, no redirects) and applies it to the original photo.

SpaceWorks decodes the answer and **rejects** it, with a typed code, when it is not a PNG (`response_not_png`), has no
alpha channel or is fully opaque (`response_no_alpha`), is fully transparent (`response_empty`), is larger than 16 MB
(`response_too_large`), or has a different aspect ratio than the photo sent, more than 1% off, or an edge over
4096 px (`response_shape_mismatch`). The cut-out may be smaller than the input; keep the same proportions.

Any other success status (`201`, `204`, a `3xx` redirect, which is never followed) or content type is a final
`invalid_response` / `response_not_png`.

**Answer, failure**: any non-2xx status with `Content-Type: application/json`:

```json
{"error": {"code": "no_subject_found", "message": "No person detected", "retryable": false}}
```

See [Errors](errors.md) for the codes and their statuses.

## `GET /v1/health`

Signed like any other request (empty body). Answer `200 application/json`:

```json
{"status": "ok", "contract": "1", "capabilities": ["image.remove_background"]}
```

**Test connection** in settings calls this, waiting 5 s to connect and at most 15 s in total, and reads at most 64 KB
of the answer. It fails when the answer is not `200 application/json`, when `contract` is not `"1"` or when the
capability is missing. Each person can run it 10 times a minute.

## Limits a provider must honour

| Limit | Value |
|---|---|
| Input types | `image/png`, `image/jpeg`, `image/webp` (accept all three) |
| Input size | up to 8 MB |
| Input dimensions | longest edge up to 4096 px (SpaceWorks normally sends at most 1200 px) |
| Output size | up to 16 MB; the PNG (or mask) is also refused, before it is decoded, if its header claims an edge over 4096 px |
| Time | SpaceWorks waits 5 s to connect and 65 s in total for the whole answer (a slow trickle counts against it); slower answers are retried as `provider_timeout` |
| Redirects | never followed |
| Addresses | your host name is looked up once per call and every answer must be allowed (space setting: public addresses only; carrier-grade NAT and cloud metadata addresses count as not public); SpaceWorks connects to that exact address. A `mask_url` is always held to the public-https rule |
| Clock | within 300 s of SpaceWorks' clock |

## Try it with curl

The signature covers the **exact request body**, so build the body in a file, hash that file and send those same
bytes. This script needs only `bash`, `curl` and `openssl`:

```bash
SECRET='your-shared-secret-at-least-16-chars'
URL='https://eraser.example.org'          # the provider address you will enter in settings
P='/v1/remove-background'                  # the path as sent, including any prefix in $URL
B='swboundary7f3a9c'

# 1. The multipart body (one part named "image").
{ printf -- "--$B\r\nContent-Disposition: form-data; name=\"image\"; filename=\"photo.jpg\"\r\nContent-Type: image/jpeg\r\n\r\n"
  cat photo.jpg
  printf -- "\r\n--$B--\r\n"; } > body.bin

# 2. Sign: SW-IMAGE-ADAPTER-V1 LF METHOD LF PATH LF TIMESTAMP LF NONCE LF BODY_SHA256
TS=$(date +%s); NONCE=$(openssl rand -hex 16)
DIGEST=$(openssl dgst -sha256 -hex body.bin | awk '{print $NF}')
SIG=$(printf 'SW-IMAGE-ADAPTER-V1\nPOST\n%s\n%s\n%s\n%s' "$P" "$TS" "$NONCE" "$DIGEST" \
      | openssl dgst -sha256 -hmac "$SECRET" -hex | awk '{print $NF}')

# 3. Send it.
curl -sS "$URL$P" -H "Content-Type: multipart/form-data; boundary=$B" \
  -H 'X-SW-Adapter-Version: 1' -H "X-SW-Timestamp: $TS" -H "X-SW-Nonce: $NONCE" \
  -H "X-SW-Body-SHA256: $DIGEST" -H "X-SW-Signature: v1=$SIG" \
  --data-binary @body.bin -o cutout.png -w '%{http_code} %{content_type}\n'
```

A working provider prints `200 image/png` and `cutout.png` has a transparent background. Use a fresh nonce for every
call: a repeated nonce answers `409 replayed_nonce`.

For the health check, sign `GET` and `/v1/health` with the digest of an empty body
(`e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855`) and send the same headers without a body.
