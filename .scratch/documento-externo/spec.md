Status: ready-for-agent

# Spec: Firma de Documento Externo

Vocabulary: `CONTEXT.md`. Decisions: ADRs 0002–0005.

## Problem Statement

A Sistema Emisor needs the Tribunal to sign PDFs that do not live in TAPIR. Today the only batch PDF paths protocolize, write the TAPIR filesystem, unlock tasks, and can apply Firma del Sistema. Those PDFs cannot go through that machinery. Orden de Pago files also have no Campo de Firma: the stamp must sit on an almost-invisible Marcador TRIB (`@TRIB` / `@trib`). Other Documentos Externos still use an existing Campo de Firma. The caller still needs USB-token Firma Digital (init → Tuquito Signing Batch → end) and person-named Firma Electrónica, in lote, without breaking stamp clock consistency.

## Solution

Two new routes, `/firmaexterna` and `/firmaexternaend`, isolated from TAPIR persist and from `/firmalote`. The caller declares `es_op`. OP is anchored on the unique Marcador TRIB; non-OP on `firma_lugar`. The signed PDF comes back in the HTTP body. Firma Digital reuses the existing Tuquito two-step and Redis-frozen clock. Firma Electrónica finishes in init with the server local certificate. Auth is `X-API-Key` on these two routes only.

## User Stories

1. As a caller, I want to send a lote of Documentos Externos that never enter TAPIR, so that a Sistema Emisor can get signed PDFs without protocolizar.
2. As a caller, I want `/firmaexterna` and `/firmaexternaend` as a dedicated pair, so that `/firmalote` keeps its TAPIR behaviour.
3. As a TAPIR caller, I want `/firmalote` and `/firmaloteend` unchanged and without API key, so that existing integrations keep working.
4. As a caller, I want to authenticate `/firmaexterna` and `/firmaexternaend` with header `X-API-Key`, so that those routes are not open like TAPIR.
5. As a caller, I want HTTP 401 when the API key is missing or wrong, so that I can tell auth failure from a signing error.
6. As an operator, I want a single API key from the environment, so that we can add per-Sistema Emisor keys later without blocking this work.
7. As a firmante, I want Firma Digital with the USB token, so that the PAdES signature is bound to my Certificate Selection.
8. As a firmante, I want one PIN to create a Signing Transaction that authorizes exactly one Signing Batch of Documentos Externos, so that I do not re-enter the PIN per PDF.
9. As a caller, I want `/firmaexterna` with `firma_digital=true` to return compact `dataToSign` in request order, so that I can POST that list unchanged to Tuquito `/rest/sign`.
10. As a caller, I want `/firmaexternaend` to accept those same successful items plus `signatureValue` and `certificates`, so that DSS can embed the token signature.
11. As a caller, I want `/firmaexternaend` to return compact `signedPdfs` in the same order as `docsSigned`, so that I can pair each PDF with its `id_documento`.
12. As a caller, I want `/firmaexternaend` not to carry `firma_digital`, so that the end route is always Firma Digital.
13. As a caller, I want Firma Electrónica to complete in `/firmaexterna` with the server local certificate, so that a person (`firma_nombre`) can sign without a token.
14. As a caller, I want Firma Electrónica to return compact `signedPdfs` on init, so that there is no second round trip.
15. As a caller, I want Firma Electrónica never to call `/firmaexternaend`, so that I cannot accidentally finalize an electronic lote.
16. As a caller, I want HTTP 400 if I POST `/firmaexternaend` for an electronic lote, so that the contract is explicit.
17. As a caller, I want `firma_digital` at lote level, so that a Signing Batch cannot mix Firma Digital and Firma Electrónica.
18. As a caller, I want HTTP 400 if a lote would mix modes, so that Tuquito and certificates stay unambiguous.
19. As a caller, I want `certificates` required when `firma_digital=true`, so that DSS can build `dataToSign`.
20. As a caller, I want HTTP 400 if Firma Electrónica includes `certificates`, so that I do not send token certs down the local-cert path.
21. As a caller, I want to declare `es_op` per item, so that placement is never inferred from the PDF.
22. As a caller, I want an Orden de Pago to be signed on the unique Marcador TRIB, so that the stamp sits where the Sistema Emisor left the almost-invisible origin.
23. As a caller, I want `@TRIB` and `@trib` to count as the same Marcador TRIB, so that case does not reject a valid OP.
24. As a caller, I want the stamp’s top-left to coincide with the Marcador TRIB’s top-left, growing right and down, so that the visual matches the agreed origin.
25. As a caller, I want the stamp size to match the current sello (~320×80 in the DSS field), so that OP looks like today’s TAPIR stamp.
26. As a caller, I want an OP item to fail if the PDF has zero Marcador TRIB, so that we never guess a Campo de Firma.
27. As a caller, I want an OP item to fail if the PDF has more than one Marcador TRIB, so that we never pick “the first” in silence.
28. As a caller, I want the Marcador TRIB to remain in the signed PDF, so that we do not mutate the source layout beyond the signature.
29. As a caller, I want an OP item that also sends `firma_lugar` to fail that item only, so that a Campo de Firma cannot override TRIB.
30. As a caller, I want a non-OP to require `firma_lugar`, so that the signature calza in the existing Campo de Firma.
31. As a caller, I want a non-OP item to fail if `firma_lugar` is missing, so that we do not invent coordinates.
32. As a caller, I want a non-OP item to fail if that Campo de Firma is not in the PDF, so that DSS is not called with a dead field id.
33. As a caller, I want a non-OP that happens to contain `@TRIB` to ignore the marker, so that `es_op=false` stays authoritative.
34. As a caller, I want one visible signature per item, so that a second signature is another request with another PDF or another anchor.
35. As a caller, I want no `firma_cierra`, no `firma_lugarcierre`, and no Firma del Sistema, so that closing a TAPIR document cannot leak into this flow.
36. As a caller, I want no protocolizar, no TAPIR DB unlock, and no filesystem write, so that Documento Externo cannot touch TAPIR state.
37. As a caller, I want the signed bytes only in the HTTP response, so that I own persistence on the Sistema Emisor side.
38. As a caller, I want each item to send `pdf`, `es_op`, `id_documento`, `id_firmante`, `firma_nombre`, `firma_sello`, and `firma_area`, so that the sello can be drawn as today.
39. As a firmante, I want the sello to use “Firmado digitalmente por” for Firma Digital and “Firmado electrónicamente por” for Firma Electrónica, so that the label matches the mode.
40. As a caller, I want not to send `id_sello`, `id_oficina`, `path_file`, `firma_cuil`, or TAPIR `id_doc`, so that DB-only fields are not required.
41. As a caller, I want a lote that mixes OP and non-OP items (same signing mode) to be valid, so that one PIN can cover both layouts.
42. As a caller, I want item failures (missing TRIB, missing field, OP+`firma_lugar`) not to abort the lote, so that valid PDFs still enter the Signing Batch.
43. As a caller, I want `docsSigned` and `docsNotSigned` to be `id_documento` values in request order, without sorting, so that I can zip them with compact `dataToSign` / `signedPdfs`.
44. As a caller, I want `dataToSign` and `signedPdfs` to contain only successes, in request order, with no nulls, so that Tuquito never sees a hole in the Signing Batch.
45. As a caller, I want `errors[].id_documento` and `errors[].message`, so that I do not have to map TAPIR’s `idDocFailed`.
46. As a caller, I want HTTP 200 with `status: false` when the lote JSON is valid but some items fail, so that partial success is not an HTTP 400.
47. As a caller, I want HTTP 400 for lote-level contract errors (empty `pdfs`, electronic with `certificates`, digital without `certificates`, mixed modes), so that I do not start Tuquito on a bad lote.
48. As a caller, I want `/firmaexternaend` after a successful finalize of the same fingerprint to return HTTP 409 without `signedPdfs`, so that I know I must keep the first response.
49. As a caller, I want a retry of digital init with the same fingerprint to reuse the frozen clock and `dataToSign`, so that the sello time does not jump between 23:59 and 00:01.
50. As a caller, I want that frozen clock to be `America/Argentina/Tucuman`, so that the sello is not the container’s naive TZ.
51. As a caller, I want a retry of Firma Electrónica with the same fingerprint to re-sign with a new clock, so that electronic stays one-shot without storing PDFs in Redis.
52. As a caller, I want a second concurrent `/firmaexterna` for the same fingerprint to get busy immediately, so that two in-flight signatures cannot race.
53. As a caller, I want that busy not to block the HTTP worker waiting on the other lote, so that a PIN in another transaction cannot hang this request.
54. As a caller, I want digital end without a pending context to fail that item (or 409 if already finalized), so that I cannot embed a signature on the wrong PDF.
55. As a caller, I want the end request to send the same PDF bytes as init (same sha256), so that a swapped file cannot reuse a frozen clock.
56. As a caller, I want Redis identity `(id_documento, id_firmante, ancla, sha256 of init PDF)`, so that OP vs Campo de Firma cannot collide on the same file.
57. As an operator, I want no change to Tuquito itself, so that Origin-bound Signing Transactions keep working as ADR 0001.
58. As a caller, I want DSS to receive coordinates for OP (no `fieldId`) and `fieldId` for non-OP, so that placement matches the declared type.
59. As a caller, I want OP coordinates to use the page where the Marcador TRIB actually is, so that a marker on page 2 is not signed on the last page.
60. As a caller, I want an empty `pdfs` array to be HTTP 400, so that we never create an empty Signing Transaction.
61. As a caller, I want duplicate `id_documento` in the same lote to fail the extra items, so that lock identity stays unique inside one request.
62. As a firmante, I want already-signed PDFs to be signable again as a new item (new bytes → new sha256), so that a second Campo de Firma can be used on a later request.
63. As an operator, I want `/firmaexterna` never to call TAPIR protocolize or Yunga close, so that Firma del Sistema cannot appear on a Documento Externo.

## Implementation Decisions

- New HTTP pair `/firmaexterna` (init) and `/firmaexternaend` (digital finalize). Do not add a flag to `/firmalote`. ADR 0002.
- Auth: header `X-API-Key` compared to one environment secret. Only these two routes. Missing/mismatch → 401. TAPIR routes stay unauthenticated.
- Lote body: `firma_digital` (boolean, required, lote-level) and, when digital, `certificates` as today (lote-level). `pdfs` array of items.
- Item body: `pdf` (base64), `es_op` (boolean), `id_documento`, `id_firmante`, `firma_nombre`, `firma_sello`, `firma_area`. If `es_op` is false, `firma_lugar` is required. If `es_op` is true, `firma_lugar` present → item error. End items add `signatureValue`. ADR 0003, 0004.
- Electronic lote that includes `certificates` → HTTP 400. Digital lote without `certificates` → HTTP 400. Mixed `firma_digital` cannot happen because the flag is not per-item; do not accept a second mode field per item.
- `/firmaexternaend` implies Firma Digital: no `firma_digital` field. Requires `pdfs`, `certificates`, and per-item `signatureValue`. Calling it without a matching digital init context fails the item; already-finalized fingerprint → HTTP 409 for that conflict (lote may still be 409 when the whole request is a replay of a finished end). Prefer 409 when the caller retries a fully successful end of the same batch fingerprint; item-level finalized errors if only some items are replayed. Simplest consistent rule: each item whose Redis state is `finalized` contributes an error with that `id_documento`; if every item is finalized and none succeed, HTTP 409. If some items are still pending, HTTP 200 with those item errors and successes as compact lists.
- Response: `status`, `message`, `docsSigned`, `docsNotSigned`, `errors`. Digital init adds `dataToSign`. Electronic init and digital end add `signedPdfs`. Arrays of successes are compact and in request order. `docsSigned` / `docsNotSigned` are `id_documento` strings/ids, never sorted. `errors[]` uses `id_documento` + `message`. ADR 0004.
- HTTP: 401 auth; 400 lote contract; 409 successful-end replay with no PDF body; 200 otherwise, with `status: false` when any item failed.
- Placement OP: locate exactly one Marcador TRIB (`@TRIB` or `@trib`) in the PDF (annotation or equivalent text). Top-left of that marker is the DSS signature field origin; width/height match the current sello (~320×80); page is the marker’s page. Empty `fieldId`. Non-OP: existing DSS `fieldId` = `firma_lugar`, same as TAPIR. Leave the marker in the file.
- Crypto and sello: reuse the current PAdES + sello pipeline (DSS `getDataToSign` / `signDocument`, local cert for electronic, token path for digital). Do not call protocolize, unlock, or file stage/promote.
- Clock: `America/Argentina/Tucuman`. Digital init writes Redis context with frozen `timestamp_ms` and `datetimesigned`; init retry with the same fingerprint reuses them. Electronic does not freeze for replay; a later request re-signs. ADR 0005.
- Redis fingerprint: `(id_documento, id_firmante, ancla, sha256(pdf at init))` where `ancla` is `OP` for Orden de Pago and the Campo de Firma id otherwise. Reuse the existing pending / finalizing / finalized / busy / mismatch semantics. Entity lock on that identity for both modes; contention returns busy immediately (item error), no HTTP wait.
- Digital init retry: same fingerprint → reuse context (`dataToSign` / clock). Digital end success → `finalized`; retry end → 409 or item finalized, never the PDF. Electronic retry → new signature, new clock, still under the lock so two in-flight requests cannot both sign.
- Sello labels: digital “Firmado digitalmente por”; electronic “Firmado electrónicamente por”. Same logo and text fields as today’s person stamp. No Yunga/system stamp.
- Tuquito is unchanged. The caller compactifies by construction: the API never returns null slots.
- Do not persist signed PDFs in Redis or on disk.

## Testing Decisions

- One seam: Flask `test_client` against `POST /firmaexterna` and `POST /firmaexternaend`.
- Mock collaborators: DSS (record `fieldId` / `originX` / `originY` / `page` / image / signingDate), Redis context/lock, local certificate, sello image bytes. Do not assert on internal helper names.
- Drive Marcador TRIB through this seam with fixture PDFs (zero, one, two markers; mixed case `@trib`; marker not on the last page). The DSS mock is how we observe coordinates. Non-OP fixtures expose an AcroForm field name.
- Good tests: HTTP status, JSON contract (`docsSigned` order, compact `dataToSign`/`signedPdfs`, `errors[].id_documento`), auth, lote-vs-item errors, no TAPIR persist calls, clock reuse vs electronic re-sign, busy, 409 without PDF.
- Bad tests: Redis key strings, private locator function names, DSS JSON copied wholesale, snapshot of the PNG sello.
- Prior art: Tuquito route tests already use Flask `test_client`. TAPIR `SignaturesService` unittests stay as they are and are not the seam for this feature.

## Out of Scope

- Changing Tuquito, Origin binding, or Signing Transaction (ADR 0001).
- Changing `/firmalote`, `/firmaloteend`, `/firmaloro`, JADES, or PDF validation.
- Protocolizar, Firma del Sistema, TAPIR DB, filesystem persist, `firma_cierra`.
- Inferring OP from the PDF; creating a missing Campo de Firma; deleting the Marcador TRIB.
- Storing signed PDFs for replay; re-embedding on end retry via DSS.
- Per-Sistema Emisor API keys, mTLS, API key on TAPIR routes.
- Mixing Firma Digital and Firma Electrónica in one lote.
- PHP/Sistema Emisor client work; UI.
- Multiple visible signatures in one item.
- Exact millimetre tuning of the V°B° box beyond the current sello size.

## Further Notes

- Sample OP from the Sistema Emisor is a SAFyC “Comprobante de Ejecución del Gasto”; `@TRIB` is almost invisible in extracted text.
- Next step in the Matt flow: `/to-tickets` into `.scratch/documento-externo/issues/`, blockers first, then `/implement` per ticket.
