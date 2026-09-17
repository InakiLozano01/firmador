---
status: accepted
---

# Documento Externo lives on its own endpoints

`/firmalote` protocolizes, writes the TAPIR filesystem, unlocks tasks, and has no auth. Documento Externo must not do any of that, and it must not receive a Firma del Sistema. We therefore add `/firmaexterna` and `/firmaexternaend` instead of a flag on the TAPIR routes, return the signed PDF in the response, and put `X-API-Key` only on the new pair so existing callers stay unchanged.

## Considered Options

- Reuse `/firmalote` with `es_externo` and skip persist — easy to miss a close/protocolize path later, and API-key would hit TAPIR or stay absent.
- New routes, no TAPIR I/O — chosen.

## Consequences

A future reader who “just adds protocolize” to the new pair is undoing this boundary. The caller, not TAPIR disk, owns the signed bytes.