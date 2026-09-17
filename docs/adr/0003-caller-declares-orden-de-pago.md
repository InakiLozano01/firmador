---
status: accepted
---

# The caller declares whether a Documento Externo is an Orden de Pago

Placement is different for OP (unique Marcador TRIB, top-left of the stamp) and for everything else (existing Campo de Firma). Inferring OP from `@TRIB` would sign the wrong place when a non-OP contains that text, or silently fall back when an OP is missing it. The caller sends `es_op`; we do not infer. An OP that also sends `firma_lugar`, or a non-OP that omits it, is an item error — the rest of the batch still runs.

## Considered Options

- Infer OP if `@TRIB` exists — rejected; the marker is an anchor, not a type.
- Caller flag with fallback to the field when the marker is missing — rejected; an OP without TRIB must fail that item.
- Caller flag, exclusive anchors — chosen.