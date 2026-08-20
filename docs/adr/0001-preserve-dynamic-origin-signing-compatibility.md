---
status: accepted
---

# Preserve dynamic-origin signing compatibility

Tuquito must continue supporting existing web callers whose origins can change, without adding another confirmation after the single PIN prompt. We therefore do not require a fixed origin allowlist or a new backend-signed authorization token yet; instead, each one-shot Signing Transaction is bound to the origin that opened it, displays that origin in the existing PIN window, validates `tokenId` and `keyId`, and is consumed after one batch sign.

## Consequences

This preserves the current user experience and caller compatibility, but it does not fully prevent a malicious origin from initiating its own PIN flow and deceiving a user. Backend-signed short-lived authorization remains the preferred future hardening when compatibility permits.
