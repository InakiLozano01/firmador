# Configuración de Certificados de Argentina para DSS

Este documento explica cómo configurar DSS para confiar en certificados de Argentina y buscar CRLs/OCSP.

## Paso 1: Obtener los Certificados Raíz de Argentina

Los certificados raíz de Argentina generalmente provienen de:
- **AC RAIZ (Autoridad Certificante Raíz)**: Certificado raíz del Estado Argentino
- **AC Subordinadas**: Certificados intermedios de diferentes organismos

### Opciones para obtener los certificados:

1. **Desde el navegador**:
   - Abre un certificado emitido en Argentina
   - Exporta la cadena completa de certificados
   - Guarda los certificados raíz e intermedios en formato `.cer` o `.crt`

2. **Desde sitios oficiales**:
   - Busca en el sitio oficial de la autoridad certificante de Argentina
   - Descarga los certificados raíz en formato DER (.cer) o PEM (.crt)

3. **Desde un certificado existente**:
   ```bash
   # Extraer certificados de un archivo PKCS12
   openssl pkcs12 -in certificado.p12 -nokeys -clcerts -out cert-intermedio.cer
   openssl pkcs12 -in certificado.p12 -nokeys -cacerts -out cert-raiz.cer
   ```

## Paso 2: Crear el Keystore con los Certificados

Una vez que tengas los certificados raíz de Argentina, crea un keystore PKCS12:

```bash
# Crear un keystore vacío
keytool -genkeypair -alias dummy -keyalg RSA -keysize 2048 -keystore argentina-truststore.p12 -storetype PKCS12 -storepass dss-password -dname "CN=Dummy" -validity 1

# Eliminar la clave dummy (solo queremos certificados de confianza)
keytool -delete -alias dummy -keystore argentina-truststore.p12 -storepass dss-password

# Importar cada certificado raíz
keytool -import -alias "ac-raiz-argentina" -file ac-raiz.cer -keystore argentina-truststore.p12 -storetype PKCS12 -storepass dss-password -trustcacerts -noprompt

# Importar certificados intermedios si es necesario
keytool -import -alias "ac-intermedia-1" -file ac-intermedia-1.cer -keystore argentina-truststore.p12 -storetype PKCS12 -storepass dss-password -trustcacerts -noprompt
```

### Alternativa usando OpenSSL (si prefieres):

```bash
# Convertir certificado PEM a DER si es necesario
openssl x509 -in cert.pem -out cert.cer -outform DER

# Crear keystore desde certificados PEM
# (requiere herramientas adicionales o usar keytool después de convertir)
```

## Paso 3: Colocar el Keystore en el Proyecto

1. Coloca el archivo `argentina-truststore.p12` en:
   ```
   dssapp/dss-demo-webapp/src/main/resources/argentina-truststore.p12
   ```

2. Actualiza `dss.properties` con la ruta y contraseña correctas:
   ```properties
   trusted.source.keystore.type = PKCS12
   trusted.source.keystore.filename = argentina-truststore.p12
   trusted.source.keystore.password = dss-password
   ```

## Paso 4: Configuración de CRL/OCSP

DSS ya está configurado para:
- **CRL**: Buscar automáticamente en las URLs de CRL Distribution Points (CDP) de los certificados
- **OCSP**: Buscar automáticamente en las URLs de OCSP de los certificados
- **AIA (Authority Information Access)**: Buscar certificados intermedios automáticamente

Las fuentes están configuradas en `DSSBeanConfig.java`:
- `cachedCRLSource()`: Busca CRLs desde las URLs en los certificados
- `cachedOCSPSource()`: Busca respuestas OCSP desde las URLs en los certificados
- `cachedAIASource()`: Busca certificados intermedios desde las URLs en los certificados

## Paso 5: Verificar la Configuración

1. **Reinicia el servidor DSS** para cargar los nuevos certificados de confianza

2. **Verifica los logs** al iniciar:
   ```
   INFO | main | eu.europa.esig.dss.web.config.DSSBeanConfig | Loading trusted certificates from argentina-truststore.p12
   ```

3. **Prueba con un certificado de Argentina**:
   - Intenta firmar un documento con un certificado de Argentina
   - Verifica que DSS pueda validar la cadena de certificados
   - Verifica que DSS pueda obtener CRLs/OCSP desde las URLs de Argentina

## Paso 4: Políticas de Validación

Las políticas de validación (`constraint.xml` y `certificate-constraint.xml`) definen las reglas que DSS aplica al validar firmas y certificados.

### Política Personalizada para Argentina

Se ha creado una política personalizada (`constraint-argentina.xml`) que permite SHA1 con nivel WARN (en lugar de FAIL) para acomodar certificados antiguos de Argentina que pueden usar SHA1 en:
- **CRLs (Certificate Revocation Lists)**: Algunos certificados intermedios de Argentina firman sus CRLs con SHA1
- **Cadenas de certificados**: Algunos certificados pueden usar SHA1 en la firma de certificados intermedios

**Esta política está configurada por defecto** en `dss.properties`:
```properties
default.validation.policy = policy/constraint-argentina.xml
```

### Cambios Principales en la Política

1. **`AlgoExpirationDate Level="WARN"`** (en lugar de `FAIL`): Permite SHA1 con advertencia en lugar de fallar la validación
2. **SHA1 Date="2009"**: Aunque SHA1 expiró en 2009, la política ahora muestra una advertencia en lugar de un error

### Si Quieres Usar la Política por Defecto de la UE

Si prefieres usar la política estricta de la UE (que rechazará SHA1), cambia en `dss.properties`:
```properties
default.validation.policy = policy/constraint.xml
```

**Nota**: Esto causará que las firmas con certificados de Argentina que usan SHA1 fallen la validación.

### Si Necesitas una Política Personalizada

Si encuentras que las políticas por defecto son demasiado estrictas para tus certificados de Argentina, puedes:

1. **Copiar las políticas por defecto** desde `dss-policy-jaxb/src/main/resources/policy/`
2. **Modificar los niveles de validación** (FAIL → WARN o IGNORE) para reglas específicas
3. **Guardar como** `policy/constraint-argentina.xml` en `src/main/resources/`
4. **Actualizar** `dss.properties`:
   ```properties
   default.validation.policy = policy/constraint-argentina.xml
   ```

### Niveles de Validación

- **FAIL**: La validación falla si no se cumple (obligatorio)
- **WARN**: Genera una advertencia pero permite la validación
- **INFORM**: Solo informa, no afecta la validación
- **IGNORE**: Ignora completamente la regla

## Notas Importantes

- **Revocación para cadenas no confiables**: Ya está habilitada (`setCheckRevocationForUntrustedChains(true)`)
- **URLs de CRL/OCSP**: DSS buscará automáticamente en las URLs especificadas en los certificados
- **Firewall/Red**: Asegúrate de que el servidor DSS tenga acceso a las URLs de CRL/OCSP de Argentina

## Diferencia entre Validación Básica y Calificación (Qualification)

### Validación Básica (Basic Validation) ✅

La **validación básica** verifica que:
- La cadena de certificados llegue a un trust anchor (certificado raíz confiable)
- Los certificados no estén revocados
- Los certificados no estén expirados
- Las firmas sean válidas

**Esto SÍ funciona con tu keystore personalizado**. Si ves en el reporte:
```json
"CertificateChain": {
    "Certificate": [
        {
            "trusted": true  // ✅ El keystore funciona correctamente
        }
    ]
}
```

Significa que la validación básica está funcionando correctamente.

### Calificación (Qualification) ⚠️

La **calificación** es un proceso específico de **eIDAS** (Reglamento Europeo) que determina si un certificado puede ser considerado "Qualified" (Calificado) según los estándares de la UE.

**Para la calificación, el certificado DEBE estar en una Trusted List oficial de la UE**. Los certificados de Argentina NO están en estas listas, por lo que:

- ❌ **Nunca podrán ser "Qualified"** según eIDAS
- ⚠️ **Verás el error**: `"Unable to build a certificate chain up to a trusted list!"` en `QualificationDetails`

**Esto es NORMAL y ESPERADO** para certificados no-UE. No es un error de configuración.

### Resumen

| Aspecto | Validación Básica | Calificación (eIDAS) |
|---------|-------------------|----------------------|
| **Funciona con keystore personalizado** | ✅ SÍ | ❌ NO |
| **Requiere Trusted Lists oficiales UE** | ❌ NO | ✅ SÍ |
| **Certificados de Argentina** | ✅ Funcionan | ❌ No pueden ser Qualified |
| **Resultado esperado** | `PASSED` o `INDETERMINATE` | `FAILED` (esperado) |

### ¿Es un problema?

**NO**. El error de calificación es esperado para certificados de Argentina. Lo importante es que:
1. ✅ La validación básica funcione (certificado raíz marcado como `trusted: true`)
2. ✅ La firma sea válida (`Indication: PASSED` o `INDETERMINATE` sin errores críticos)
3. ✅ Los certificados no estén revocados ni expirados

La calificación solo es relevante si necesitas cumplir con el reglamento eIDAS de la UE, lo cual no aplica para certificados de Argentina.
- **Timeouts**: Si las URLs de Argentina son lentas, considera aumentar los timeouts en `dss.properties`:
  ```properties
  dataloader.connection.timeout = 10000  # 10 segundos
  dataloader.connection.request.timeout = 10000
  ```
- **Políticas de Validación**: Con los certificados en el keystore de confianza, las políticas por defecto deberían funcionar sin modificaciones

## Troubleshooting

Si DSS no puede validar certificados de Argentina:

1. **Verifica que el keystore se carga correctamente**: Revisa los logs al iniciar
2. **Verifica acceso a URLs de CRL/OCSP**: Prueba acceder a las URLs desde el servidor
3. **Verifica la cadena de certificados**: Asegúrate de incluir todos los certificados intermedios necesarios
4. **Revisa los logs de DSS**: Busca errores relacionados con validación de certificados
