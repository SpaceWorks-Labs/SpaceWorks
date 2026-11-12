---
title: Image Adapter API: errors
group: Reference
order: 64
summary: The typed error codes a provider answers with and the codes SpaceWorks records, with what is retried.
---

# Errors

A provider answers a failure with a non-2xx status and a JSON body:

```json
{"error": {"code": "rate_limited", "message": "Try again shortly", "retryable": true}}
```

`code` must be one of the codes below. SpaceWorks maps by the code first; if the body is missing or the code is
unknown it falls back to the status (`429` is `rate_limited`, `503` is `unavailable`, other `5xx` is `internal_error`,
anything else is `invalid_response`, not retried). Whether a code is retried is decided by SpaceWorks (the table
below); the `retryable` field is informational and never makes an unknown code retryable.

## Codes a provider answers with

| Code | HTTP | Meaning | Retried |
|---|---|---|---|
| `invalid_signature` | 401 | Headers missing, digest or HMAC wrong | no |
| `stale_timestamp` | 401 | Timestamp more than 300 s from the provider's clock | no |
| `replayed_nonce` | 409 | The nonce was seen in the last 600 s | no |
| `unsupported_media_type` | 415 | The image is not PNG, JPEG or WebP | no |
| `payload_too_large` | 413 | The image is over 8 MB | no |
| `dimensions_too_large` | 422 | The longest edge is over 4096 px | no |
| `unreadable_image` | 422 | The bytes do not decode as an image | no |
| `no_subject_found` | 422 | No person or subject found to keep | no |
| `rate_limited` | 429 | Too many requests | yes |
| `unavailable` | 503 | Starting up or overloaded | yes |
| `internal_error` | 500 | Unexpected failure | yes |

## Codes SpaceWorks itself records

These appear on a failed cut-out in the card photo panel, in plain words, and in the audit log as `error_code`.

| Code | Meaning | Retried |
|---|---|---|
| `not_configured` | No provider is set up for the space, or the switch went off | no |
| `provider_unreachable` | Connection refused, DNS or TLS failure | yes |
| `provider_timeout` | No answer within 60 s | yes |
| `url_not_allowed` | A space-level address that is not public https, or a `mask_url` that is missing or not public https | no |
| `input_not_allowed` | The stored photo is outside the contract (type, size, 4096 px) | no |
| `photo_missing` | The card's photo was removed or replaced before the job ran | no |
| `invalid_response` | Not a usable answer (bad JSON, wrong contract version) | no |
| `response_not_png` | Answered `200` but not with a PNG | no |
| `response_no_alpha` | The PNG has no alpha channel, or nothing was removed | no |
| `response_empty` | The PNG is fully transparent | no |
| `response_too_large` | Over 16 MB | no |
| `response_shape_mismatch` | Different proportions, or over 4096 px | no |
| `mask_unreachable` | The `mask_url` could not be fetched | no |

A retryable failure is tried again up to 4 times in total, waiting 30 s, 2 min and 10 min between attempts. After
that, or for any non-retryable code, the job is marked **failed** with that code and nothing on the card changes.
