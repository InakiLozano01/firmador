---
status: accepted
---

# A Documento Externo batch is one signing mode, and Tuquito arrays stay compact

`/firmalote` can mix Firma Electrónica and Firma Digital in one `pdfs` list, and it sorts `docsSigned` out of `dataToSign` order. Documento Externo does not: `firma_digital` is batch-level, mixed modes are HTTP 400, and `certificates` are required for digital and forbidden for electronic. `dataToSign` / `signedPdfs` / `docsSigned` are compact successes in request order, never sparse nulls and never sorted, so the list can be posted to Tuquito as one Signing Batch. `/firmaexternaend` is digital-only; the caller resubmits only those successful items, each with `signatureValue`.