---
status: accepted
---

# Documento Externo does not store the signed PDF

TAPIR can lose the HTTP body and still have the file on disk. We have no disk and refused to keep base64 PDFs in Redis. After a successful `/firmaexternaend`, a retry is 409 with no PDF — the caller must keep the first response. Firma Digital still freezes `timestamp_ms` and `datetimesigned` in Redis at init (`America/Argentina/Tucuman`) so init/end and init retries stay the same stamp. Firma Electrónica is one-shot and re-signs on retry. Both modes take a Redis lock; a second in-flight request gets busy immediately, and does not wait.

## Considered Options

- Replay the signed PDF from Redis — rejected; payloads are large.
- Re-embed on end retry via DSS with the frozen clock and the same `signatureValue` — rejected; 409 is simpler and matches TAPIR’s finalized state, minus the file.
- Re-sign electronic with a new clock — chosen; there is no `signatureValue` to replay.