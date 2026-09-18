# 05 — Close Documento Externo contract holes

Primary source: full-feature `/code-review` of `35db193...HEAD` (commits `9095296`…`e099719`) against `.scratch/documento-externo/spec.md`. Fix those spec holes. Fowler smells in `signatures_service.py` and duplicated prepare/lock are out of this ticket.

**What to build:** Four HTTP-seam contract holes from that review. After this ticket is green, the spec is done.

**Blocked by:** 01 — Firma Electrónica de Documento Externo con Campo de Firma; 02 — Firma Electrónica de Orden de Pago; 03 — Firma Digital de Documento Externo con Campo de Firma; 04 — Firma Digital de Orden de Pago (all done)

**Status:** done

- [x] Item missing `id_documento` fails that item (`docsNotSigned` + `errors[].id_documento`); DSS is not called for it. Other valid items in the same lote still sign. Spec L38 / L86.
- [x] Digital init retry with the same fingerprint returns the **stored** `dataToSign` and frozen Tucuman clock. Redis must keep `dataToSign` (today it only freezes `timestamp_ms` / `datetimesigned`). A retry must not depend on DSS returning the same bytes because the mock is a function of the clock. Spec L49 / L95.
- [x] The same `@TRIB` in page text and in an annotation is **one** Marcador TRIB (one origin), not “Hay más de un Marcador TRIB.” Uniqueness is one marker, not two encodings. Spec L27 / L91.
- [x] A per-item `firma_digital` is a second mode field: that item (or the lote) is HTTP 400. Spec L17–18 / L87. Lote-level `firma_digital` stays the only valid mode flag.

Covered at the existing HTTP seam (`test_firmaexterna.py`, Flask test client). DSS / Redis / local cert / sello stay mocked.

## Out of this ticket

Electronic `/firmaexternaend` **without** `firma_digital` stays item “no pending context” (HTTP 200 item errors), not lote 400. Spec L88 beats story 16: end is always digital finalize; calling it without a matching digital init context fails the item. (Sending the forbidden flag is already lote 400.)

In-memory store when Redis is missing is the test seam, not a product mode.

TAPIR DSS functions accepting optional placement kwargs stay: OP needs them; `/firmalote` is unchanged when they are omitted.

Leave: `cm`-transform TRIB math, lote 7-tuples, renaming `ancla`, extracting a fourth lock wrapper. No failing HTTP-seam case yet. Do not split `signatures_service.py` “to be clean.”
