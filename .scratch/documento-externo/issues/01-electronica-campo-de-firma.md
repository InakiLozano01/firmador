# 01 — Firma Electrónica de Documento Externo con Campo de Firma

**What to build:** A caller can POST `/firmaexterna` with `X-API-Key`, `firma_digital=false`, and non-OP items (`es_op=false` plus Campo de Firma). Each successful item comes back as a signed PDF in a compact `signedPdfs` list, in request order, without protocolizar, Firma del Sistema, or TAPIR disk/DB. `/firmalote` stays as it is and does not require the key.

**Blocked by:** None — can start immediately.

**Status:** done

- [x] `X-API-Key` missing or wrong → HTTP 401; TAPIR `/firmalote` still works without that header
- [x] Empty `pdfs` → HTTP 400; electronic lote that includes `certificates` → HTTP 400
- [x] Happy path: item with `pdf`, `es_op=false`, `id_documento`, `id_firmante`, `firma_nombre`, `firma_sello`, `firma_area`, `firma_lugar` → HTTP 200, `docsSigned` is that `id_documento` (not sorted), compact `signedPdfs` 1:1, sello labelled as Firma Electrónica
- [x] Missing `firma_lugar` or Campo de Firma absent in the PDF → that item in `docsNotSigned` + `errors[].id_documento`; other items in the same lote still sign; HTTP 200 with `status: false`
- [x] Duplicate `id_documento` in the same lote fails the extra items; DSS is called with `fieldId` = `firma_lugar`
- [x] No protocolize, unlock, filesystem persist, or Yunga/system stamp; signed bytes exist only in the response
- [x] Covered at the HTTP seam (Flask test client); DSS / Redis / local cert / sello mocked
