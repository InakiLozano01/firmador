# Document Signing

This context covers the local Tuquito flow that lets a web application use a physical cryptographic token to sign one document batch.

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

## Relationships

- A **Signing Transaction** has exactly one **Token Selection**
- A **Signing Transaction** has exactly one **Certificate Selection**
- A **Signing Transaction** authorizes exactly one **Signing Batch**
- A **Certificate Selection** binds one certificate to its matching private key

## Example dialogue

> **Dev:** "Does the user enter the PIN again when the **Signing Batch** is ready?"
> **Domain expert:** "No. The PIN creates the **Signing Transaction**, and its selected token and certificate remain authorized until that one batch is signed or the transaction expires."

## Flagged ambiguities

- “Slot” previously meant both a PC/SC reader index and a PKCS#11 slot; **Token Selection** requires an explicit mapping between them.
