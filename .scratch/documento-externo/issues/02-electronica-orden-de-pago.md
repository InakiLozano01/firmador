# 02 — Firma Electrónica de Orden de Pago (Marcador TRIB)

**What to build:** The same `/firmaexterna` electronic lote can sign an Orden de Pago: the caller sets `es_op=true` and does not send a Campo de Firma. The sello is placed with its top-left on the unique Marcador TRIB (`@TRIB` or `@trib`), on that marker’s page, growing right and down at current sello size. A lote may mix OP and non-OP items. The marker stays in the PDF.

**Blocked by:** 01 — Firma Electrónica de Documento Externo con Campo de Firma

**Status:** ready-for-agent

- [ ] `es_op=true` with exactly one Marcador TRIB → item succeeds; DSS sees rectangle + page (empty `fieldId`), not `firma_lugar`
- [ ] `@trib` and `@TRIB` both count; marker not on the last page still uses the marker’s page
- [ ] Zero markers, or more than one, → item error; no fallback to a Campo de Firma
- [ ] `es_op=true` plus `firma_lugar` → item error only; the rest of the lote continues
- [ ] `es_op=false` on a PDF that also contains `@TRIB` ignores the marker and uses the Campo de Firma
- [ ] Mixed OP + non-OP electronic lote in one request: successes compact in request order; Marcador TRIB is still present after signing
- [ ] HTTP seam with fixture PDFs (0 / 1 / 2 markers); DSS mock records origin, size, and page
