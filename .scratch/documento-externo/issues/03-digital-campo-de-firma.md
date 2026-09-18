# 03 — Firma Digital de Documento Externo con Campo de Firma

**What to build:** A caller can run Firma Digital on Documentos Externos that use a Campo de Firma: `/firmaexterna` with lote-level `firma_digital=true` and `certificates` returns compact `dataToSign` for Tuquito; `/firmaexternaend` (no `firma_digital` flag) accepts those successful items plus `signatureValue` and returns compact `signedPdfs`. Clock is frozen in Redis at init in `America/Argentina/Tucuman`. Tuquito itself is unchanged.

**Blocked by:** 01 — Firma Electrónica de Documento Externo con Campo de Firma

**Status:** done

- [x] Digital lote without `certificates` → HTTP 400; `firma_digital` is lote-level only
- [x] Digital init success → compact `dataToSign` in request order, zip-able with unsorted `docsSigned`; no `signedPdfs` yet
- [x] `/firmaexternaend` with the same PDFs, `certificates`, and per-item `signatureValue` → compact `signedPdfs`; DSS uses frozen `signingDate` and Campo de Firma
- [x] Init retry with the same fingerprint `(id_documento, id_firmante, ancla, sha256)` reuses `datetimesigned` / `dataToSign`; a swapped PDF (different sha256) does not
- [x] Successful end replay → HTTP 409 (or every item finalized) and no PDF body; caller must keep the first response
- [x] Second in-flight request for the same fingerprint gets busy immediately (no HTTP wait); electronic `/firmaexternaend` → HTTP 400
- [x] Electronic retry of the same fingerprint is allowed to re-sign with a new clock (no stored PDF); still under the lock so two in-flight electronic requests cannot both proceed
- [x] HTTP seam; Redis and DSS mocked; no TAPIR persist
