# API de Firma de Documento Externo

Guía para quien implemente la conexión desde otra aplicación (persona o agente). Describe **qué hace** el servicio y **cómo usarlo**. No hace falta conocer el interior del firmador.

**Entorno de testing**

| Qué | Valor |
| --- | --- |
| URL del firmador | `http://192.168.41.190:5000` |
| Clave | `FIRMEXT-testing-tucuman-9f3c2a7e` |
| Header | `X-API-Key: FIRMEXT-testing-tucuman-9f3c2a7e` |

Esta clave es de testing. En el navegador **no** la pongas: el backend de tu aplicación es quien llama al firmador. El JavaScript del navegador solo habla con **Tuquito** (el programa en la PC del firmante) cuando la firma es con token USB.

---

## Qué resuelve

Tu sistema (el que emite los PDFs) necesita que el Tribunal firme archivos que **no** viven en TAPIR. Mandás el PDF, el Tribunal lo firma, y te devuelve el PDF firmado **en la misma respuesta HTTP**. Vos guardás ese archivo. El firmador no protocoliza, no escribe en el disco de TAPIR y no aplica Firma del Sistema.

Hay dos rutas:

| Ruta | Cuándo |
| --- | --- |
| `POST /firmaexterna` | Siempre: inicia (y, si es electrónica, termina) |
| `POST /firmaexternaend` | Solo Firma Digital, después de que Tuquito firmó el lote |

Content-Type: `application/json`.

---

## Dos tipos de firma (elegí uno por lote)

Un **lote** es un array `pdfs`. Todo el lote es del mismo tipo. No mezcles Digital y Electrónica, y no pongas `firma_digital` adentro de cada ítem: va una sola vez, en el cuerpo del lote.

### Firma Electrónica (`firma_digital: false`)

El servidor firma con el certificado local del Tribunal, a nombre de la persona (`firma_nombre`). **Un solo POST** a `/firmaexterna`. Te vuelven los PDFs firmados. **No** llames a `/firmaexternaend`. **No** hace falta Tuquito ni JavaScript de token.

### Firma Digital (`firma_digital: true`)

La firma sale del **token USB** del firmante. Tres pasos:

1. Tu backend llama a `/firmaexterna` (con el certificado que dio Tuquito) y recibe `dataToSign`.
2. **El frontend** (JavaScript en el navegador) manda ese `dataToSign` a Tuquito. El usuario elige lector, certificado e ingresa el PIN **una vez** para todo el lote.
3. Tu backend llama a `/firmaexternaend` con cada `signatureValue` que devolvió Tuquito, y recibe los PDFs firmados.

Sin el JavaScript que habla con Tuquito, la Firma Digital no se puede completar. Ese código lo escribe **tu** aplicación web.

---

## Autenticación

Solo estas dos rutas piden clave.

```
X-API-Key: FIRMEXT-testing-tucuman-9f3c2a7e
```

| Situación | HTTP |
| --- | --- |
| Header ausente o clave incorrecta | **401** |
| Lote mal armado (vacío, modo mezclado, certificados de más o de menos) | **400** |
| Lote válido (aunque algunos PDFs fallen) | **200** |
| Reintento de un `/firmaexternaend` que ya había salido bien | **409** (sin PDFs; quedate con la primera respuesta) |

---

## Cuerpo del lote (`POST /firmaexterna`)

| Campo | Dónde | Qué es |
| --- | --- | --- |
| `firma_digital` | lote | `true` = token USB. `false` = firma electrónica en el servidor. Obligatorio. |
| `certificates` | lote | Solo si `firma_digital` es `true`. Objeto que te da Tuquito (ver más abajo). Si es electrónica, **no** lo envíes. |
| `pdfs` | lote | Array de ítems. No puede estar vacío. |

Cada ítem de `pdfs`:

| Campo | Obligatorio | Qué es |
| --- | --- | --- |
| `pdf` | sí | PDF en **Base64**. |
| `es_op` | sí | `true` si es **Orden de Pago**. `false` si es otro documento con Campo de Firma. Vos lo declarás; el servidor no lo adivina mirando el PDF. |
| `id_documento` | sí | Identificador tuyo. Sirve para armar `docsSigned` / `docsNotSigned` / `errors`. En un mismo lote no puede repetirse (el duplicado falla; el primero sigue). |
| `id_firmante` | sí | Quién firma. |
| `firma_nombre` | sí | Nombre que se dibuja en el sello. |
| `firma_sello` | sí | Cargo / sello (texto). |
| `firma_area` | sí | Área (texto). |
| `firma_lugar` | si `es_op` es `false` | Nombre del **Campo de Firma** ya existente en el PDF (el id del campo AcroForm). Si `es_op` es `true`, **no** lo envíes. |
| `signatureValue` | solo en `/firmaexternaend` | Valor que devolvió Tuquito para ese ítem. |

No hace falta mandar `id_sello`, `id_oficina`, `path_file`, `firma_cuil`, ni ids de TAPIR.

El sello dice **«Firmado digitalmente por»** o **«Firmado electrónicamente por»** según el tipo de lote.

---

## Orden de Pago vs. otro documento

### Orden de Pago (`es_op: true`)

El sello se apoya en el **Marcador TRIB**: el texto casi invisible `@TRIB` o `@trib` que tu sistema ya dejó en el PDF.

- Tiene que haber **exactamente uno** (el mismo sello puede aparecer como texto y como anotación: cuenta como uno).
- El sello se dibuja desde la esquina superior izquierda de ese marcador, hacia la derecha y abajo, en la página donde está.
- Si no hay marcador, o hay más de uno en orígenes distintos, **ese ítem** falla. El resto del lote sigue.
- Si además mandás `firma_lugar`, ese ítem falla (una OP no usa Campo de Firma).

### Otro documento (`es_op: false`)

El sello entra en un **Campo de Firma** que el PDF ya trae. Mandá su nombre en `firma_lugar`. Si falta el campo o no existe en el archivo, ese ítem falla. Si el PDF también tiene `@TRIB`, se ignora: manda `es_op`.

En un mismo lote podés mezclar OP y no-OP, siempre que el **tipo de firma** (digital o electrónica) sea el mismo.

Un ítem = una firma visible. Una segunda firma es otro pedido, con el PDF ya firmado (otros bytes).

---

## Cómo leer la respuesta

Siempre (salvo 401):

```json
{
  "status": true,
  "message": "Firma iniciada correctamente",
  "docsSigned": ["doc-1", "doc-3"],
  "docsNotSigned": ["doc-2"],
  "errors": [{ "id_documento": "doc-2", "message": "Falta el Marcador TRIB." }]
}
```

| Campo | Significado |
| --- | --- |
| `status` | `true` si **todos** los ítems salieron bien. `false` si alguno falló (HTTP sigue siendo 200). |
| `docsSigned` | `id_documento` de los que salieron bien, **en el orden en que los mandaste**, sin ordenar. |
| `docsNotSigned` | Los que fallaron, en orden de aparición. |
| `errors` | `{ "id_documento", "message" }` de cada fallo. |

Listas de éxito **compactas**: no hay `null` ni huecos. Emparejás así:

- `docsSigned[i]` ↔ `dataToSign[i]` (inicio digital)
- `docsSigned[i]` ↔ `signedPdfs[i]` (electrónica, o fin digital)

| Quién responde | Extra |
| --- | --- |
| Electrónica en `/firmaexterna` | `signedPdfs`: PDF firmado en Base64 |
| Digital en `/firmaexterna` | `dataToSign`: textos para Tuquito (sin PDFs todavía) |
| `/firmaexternaend` | `signedPdfs` |

Mandá a Tuquito **solo** el array `dataToSign` tal cual. No intercales los ítems que fallaron.

---

## Flujo 1 — Firma Electrónica (sin Tuquito)

```
Tu backend  →  POST /firmaexterna  →  signedPdfs
```

```json
{
  "firma_digital": false,
  "pdfs": [
    {
      "pdf": "<base64>",
      "es_op": false,
      "id_documento": "exp-100",
      "id_firmante": "u-42",
      "firma_nombre": "Ada Lovelace",
      "firma_sello": "Vocal",
      "firma_area": "Tribunal",
      "firma_lugar": "sig_field"
    }
  ]
}
```

Si algún PDF del lote está mal, HTTP 200, `status: false`, y `signedPdfs` solo trae los buenos.

Un reintento electrónico del mismo archivo vuelve a firmar (hora nueva del sello).

---

## Flujo 2 — Firma Digital (Tuquito + JavaScript)

Tuquito es la app de escritorio del firmante (`firma_cliente`). Escucha en **la PC del usuario**:

```
http://127.0.0.1:5000
```

(Ese puerto 5000 es de Tuquito en localhost. El firmador del Tribunal es `http://192.168.41.190:5000`. Son máquinas distintas.)

El PIN autoriza **un solo lote**. GET de certificados y POST de firma tienen que ir **desde el mismo origen** del navegador (la URL de tu webapp). Si el origen no coincide, Tuquito rechaza (403).

### Paso A — JavaScript: abrir Tuquito y obtener el certificado

El usuario tiene que tener Tuquito abierto y el token enchufado. Un GET a `/rest/certificates` abre las ventanas (lector, certificado, PIN).

```javascript
const TUQUITO = "http://127.0.0.1:5000";

async function pedirCertificadoAlToken() {
  const res = await fetch(`${TUQUITO}/rest/certificates`, {
    method: "GET",
    credentials: "omit",
  });
  const body = await res.json();
  if (!res.ok || body.status !== true) {
    throw new Error(body.message || "Tuquito no pudo leer el token");
  }
  const r = body.response;
  return {
    tokenId: r.tokenId.id,
    keyId: r.keyId,
    certificates: {
      certificate: r.certificate,
      certificateChain: r.certificateChain,
    },
  };
}
```

### Paso B — Backend: iniciar el lote

Tu servidor (con la API key) POST `/firmaexterna`:

```json
{
  "firma_digital": true,
  "certificates": {
    "certificate": "<el de Tuquito>",
    "certificateChain": ["<el de Tuquito>"]
  },
  "pdfs": [ { "...ítems como arriba..." } ]
}
```

Respuesta útil: `docsSigned` + `dataToSign` (misma longitud, mismo orden). Guardá los PDF originales de esos `id_documento`: `/firmaexternaend` tiene que recibir **los mismos bytes**.

### Paso C — JavaScript: firmar el lote en el token

```javascript
async function firmarLoteEnToken({ tokenId, keyId, dataToSign }) {
  const res = await fetch(`${TUQUITO}/rest/sign`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    credentials: "omit",
    body: JSON.stringify({
      tokenId,
      keyId,
      dataToSign, // el array compacto de /firmaexterna, sin huecos
    }),
  });
  const body = await res.json();
  if (!res.ok || body.status !== true) {
    throw new Error(body.message || "Tuquito no pudo firmar el lote");
  }
  return body.response.signatures; // un signatureValue por cada dataToSign
}
```

Ese POST consume la autorización del PIN. Un segundo POST con el mismo lote no vuelve a firmar.

### Paso D — Backend: incrustar la firma

`POST /firmaexternaend` — **sin** `firma_digital`.

Por cada `id` en `docsSigned`, el ítem lleva el mismo `pdf` de A, más `signatureValue` = `signatures[i]`.

```json
{
  "certificates": { "certificate": "...", "certificateChain": ["..."] },
  "pdfs": [
    {
      "pdf": "<mismos bytes que en el inicio>",
      "es_op": false,
      "id_documento": "exp-100",
      "id_firmante": "u-42",
      "firma_nombre": "Ada Lovelace",
      "firma_sello": "Vocal",
      "firma_area": "Tribunal",
      "firma_lugar": "sig_field",
      "signatureValue": "<signatures[0] de Tuquito>"
    }
  ]
}
```

Respuesta: `signedPdfs` compactos, alineados con `docsSigned`.

### Esqueleto para encajar en tu webapp

```javascript
async function firmarDigitalConToken(loteParaElBackend) {
  const { tokenId, keyId, certificates } = await pedirCertificadoAlToken();

  const inicio = await apiBackend("/firmaexterna", {
    firma_digital: true,
    certificates,
    pdfs: loteParaElBackend,
  });
  if (!inicio.docsSigned?.length) {
    return inicio; // nada para el token
  }

  const signatures = await firmarLoteEnToken({
    tokenId,
    keyId,
    dataToSign: inicio.dataToSign,
  });

  const pdfsEnd = inicio.docsSigned.map((id, i) => ({
    ...loteParaElBackend.find((p) => String(p.id_documento) === String(id)),
    signatureValue: signatures[i],
  }));

  return apiBackend("/firmaexternaend", {
    certificates,
    pdfs: pdfsEnd,
  });
}
```

`apiBackend` es **tu** proxy: agrega `X-API-Key` en el servidor y reenvía a `http://192.168.41.190:5000`.

---

## Reintentos y simultaneidad (Firma Digital)

- Si repetís `/firmaexterna` con el **mismo** documento (mismo `id_documento`, mismo `id_firmante`, mismo tipo OP o Campo de Firma, y **mismos bytes** de PDF), el servidor reusa la hora del sello (Tucumán) y el mismo `dataToSign`. La hora no salta de 23:59 a 00:01.
- Si cambiás el PDF (otros bytes), es un documento nuevo.
- Si otro pedido está firmando el mismo documento, el ítem vuelve con error de «firma en curso». No se queda colgado esperando el PIN de otro.
- Si `/firmaexternaend` ya había terminado bien y lo mandás otra vez: **409**, sin `signedPdfs`. Conservá la primera respuesta.
- Si llamás a `/firmaexternaend` sin haber iniciado ese PDF: el ítem falla («no hay contexto pendiente»). HTTP 200 con error de ítem, no 400 de lote.

La electrónica no congela la hora: cada POST vuelve a firmar.

---

## Errores de lote (HTTP 400)

El lote ni siquiera arranca:

- `pdfs` vacío o ausente
- `firma_digital` no es `true` ni `false`
- `firma_digital` adentro de un ítem
- Electrónica con `certificates`
- Digital sin `certificates`
- `firma_digital` en `/firmaexternaend`

Errores de **ítem** (HTTP 200, `status: false`): falta `id_documento`, falta `es_op`, falta `id_firmante`, falta o sobra `firma_lugar`, no está el Campo de Firma, no está / hay más de un Marcador TRIB, `id_documento` duplicado, firma en curso, etc. El mensaje viene en `errors[].message`.

---

## Qué no hace esta API

- No protocoliza ni cierra expedientes TAPIR.
- No guarda el PDF firmado: te lo devuelve y listo.
- No cambia `/firmalote` ni Tuquito.
- No mezcla Firma Digital y Electrónica en un lote.
- No inventa un Campo de Firma ni borra el Marcador TRIB.

---

## Prueba rápida (electrónica, lote vacío → 400)

```bash
curl -sS -X POST "http://192.168.41.190:5000/firmaexterna" \
  -H "Content-Type: application/json" \
  -H "X-API-Key: FIRMEXT-testing-tucuman-9f3c2a7e" \
  -d "{\"firma_digital\":false,\"pdfs\":[]}"
```

Esperado: HTTP 400, lote vacío. Sin header: HTTP 401.
