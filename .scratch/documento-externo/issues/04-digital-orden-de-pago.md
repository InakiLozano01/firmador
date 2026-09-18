# 04 — Firma Digital de Orden de Pago

**What to build:** Firma Digital works for Orden de Pago: init/end as in ticket 03, placement as in ticket 02 (unique Marcador TRIB). A digital lote may mix OP and non-OP items; `dataToSign` / `signedPdfs` stay compact and Tuquito-ready. 409, busy, and frozen Tucuman clock still apply.

**Blocked by:** 02 — Firma Electrónica de Orden de Pago (Marcador TRIB); 03 — Firma Digital de Documento Externo con Campo de Firma

**Status:** done

- [x] Digital OP item (`es_op=true`, no `firma_lugar`) → init `dataToSign`; end returns signed PDF with DSS rectangle on the Marcador TRIB page
- [x] Digital lote mixing OP and non-OP: compact lists in request order; failed TRIB/field items excluded from `dataToSign` and from the end payload the caller is expected to send
- [x] Same Redis fingerprint/ancla distinction (`OP` vs Campo de Firma) so an OP and a non-OP of the same bytes cannot share context
- [x] End replay still 409 without PDF; concurrent same fingerprint still busy
- [x] HTTP seam with TRIB fixtures plus digital init/end mocks
