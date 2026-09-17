# Document Signing

This context covers Tuquito token signing and the signing of documents that never enter TAPIR protocolization.

## Language

**Signing Transaction**:
A short-lived authorization created by one PIN entry and consumed by exactly one signing batch.
_Avoid_: Session, login

**Token Selection**:
The physical smartcard reader and PKCS#11 slot explicitly chosen for a Signing Transaction.
_Avoid_: First slot, default token

**Certificate Selection**:
The certificate and matching private key explicitly chosen for a Signing Transaction.
_Avoid_: First certificate, first key

**Signing Batch**:
The complete `dataToSign` list submitted in the single sign request that consumes a Signing Transaction.
_Avoid_: Signing session

**Origin**:
The HTTP origin of the web caller that opened a Signing Transaction.
_Avoid_: Document source, sistema origen

**Sistema Emisor**:
The external system that produced the PDF being signed.
_Avoid_: Origin, origen del documento

**Documento Externo**:
A PDF that is signed without protocolizing, closing, filesystem writes, or TAPIR/Yunga database sync.
_Avoid_: Documento TAPIR, expediente

**Orden de Pago (OP)**:
A Documento Externo whose visible signature is anchored on the Marcador TRIB.
_Avoid_: Comprobante, gasto (as the type flag)

**Marcador TRIB**:
The almost-invisible PDF text `@TRIB` or `@trib`; its top-left corner is the origin of the signature stamp rectangle.
_Avoid_: Signature field, firma_lugar (for OP)

**Campo de Firma**:
An existing AcroForm signature field id, the same concept as `firma_lugar` today.
_Avoid_: Marcador TRIB, coordenadas

**Firma del Sistema**:
The Yunga closing signature applied when a TAPIR document is protocolized. Documento Externo has none.
_Avoid_: Firma Electrónica, Firma Digital

**Firma Digital**:
A PAdES signature made with the USB token: init freezes the stamp clock, Tuquito signs the batch, end embeds `signatureValue`.
_Avoid_: Firma Electrónica, Firma del Sistema

**Firma Electrónica**:
A PAdES signature made with the server local certificate in one shot, still in the name of a person (`firma_nombre`).
_Avoid_: Firma del Sistema, Firma Digital

## Relationships

- A **Signing Transaction** has exactly one **Token Selection**
- A **Signing Transaction** has exactly one **Certificate Selection**
- A **Signing Transaction** authorizes exactly one **Signing Batch**
- A **Certificate Selection** binds one certificate to its matching private key
- A **Documento Externo** comes from a **Sistema Emisor**, not from an **Origin**
- An **Orden de Pago** is a **Documento Externo** anchored by a **Marcador TRIB**
- A non-OP **Documento Externo** is anchored by a **Campo de Firma**
- A **Documento Externo** never receives a **Firma del Sistema**
- A **Signing Batch** of Documentos Externos is entirely **Firma Digital** or entirely **Firma Electrónica**, never mixed
- **Firma Digital** of Documentos Externos uses `/firmaexterna` then `/firmaexternaend`
- **Firma Electrónica** of Documentos Externos completes in `/firmaexterna` and never calls `/firmaexternaend`

## Example dialogue

> **Dev:** "Does the user enter the PIN again when the **Signing Batch** is ready?"
> **Domain expert:** "No. The PIN creates the **Signing Transaction**, and its selected token and certificate remain authorized until that one batch is signed or the transaction expires."

> **Dev:** "On a Documento Externo, do we protocolize and apply Firma del Sistema?"
> **Domain expert:** "No. There is no close and no protocolize, so there is no Firma del Sistema. The person still signs with Firma Digital or Firma Electrónica."

> **Dev:** "How do we know a Documento Externo is an Orden de Pago?"
> **Domain expert:** "The caller says so. We do not infer OP from the Marcador TRIB, and we do not look at a Campo de Firma on an OP."

> **Dev:** "Can the caller send a Campo de Firma on an Orden de Pago anyway?"
> **Domain expert:** "No. That request is invalid. An OP is anchored only on the Marcador TRIB."

## Flagged ambiguities

- “Slot” previously meant both a PC/SC reader index and a PKCS#11 slot; **Token Selection** requires an explicit mapping between them.
