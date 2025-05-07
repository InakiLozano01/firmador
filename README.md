# 🔏 Firmador de Documentos - Sistema Integral de Firma Digital

<div align="center">
  <img src="./firmar_python/firma_cliente/images/logo_tribunal_para_tapir_250px.png" alt="Logo TAPIR" width="250" style="background-color: white;"/>

  [![Estado](https://img.shields.io/badge/Estado-Desarrollo%20y%20Testeo-yellow)]()
  [![Python](https://img.shields.io/badge/Python-3.12+-3776AB.svg?style=flat&logo=python&logoColor=white)]()
  [![Java](https://img.shields.io/badge/Java-17+-007396.svg?style=flat&logo=java&logoColor=white)]()
  [![Docker](https://img.shields.io/badge/Docker-Compose-2496ED.svg?style=flat&logo=docker&logoColor=white)]()
  [![PostgreSQL](https://img.shields.io/badge/PostgreSQL-14.12+-336791.svg?style=flat&logo=postgresql&logoColor=white)]()
</div>

## 📋 Descripción

Sistema integral para la firma digital de documentos que proporciona una solución robusta y segura para la gestión documental electrónica. Permite la firma digital avanzada de documentos PDF y JSON utilizando certificados digitales, con soporte para múltiples formatos de firma y validación exhaustiva. La arquitectura del sistema está compuesta por dos componentes principales que trabajan en perfecta sincronización:

- 🐍 **Servicio Python (Flask)**: Motor principal que maneja toda la lógica de firma, validación y procesamiento de documentos
- ☕ **Servicio Java**: Backend robusto que proporciona servicios DSS (Digital Signature Services) avanzados

## ✨ Características Principales

### 🔐 Firma Digital Avanzada
- 📄 Firma de documentos PDF con múltiples niveles de seguridad
- 🔗 Firma de índices JSON con validación criptográfica
- 🔑 Soporte completo para certificados digitales X.509
- 🎨 Firma visual totalmente personalizable en PDFs
  - Posicionamiento flexible
  - Diseño personalizado
  - Inclusión de logos e imágenes
- 💧 Sistema de marca de agua inteligente y configurable
- ✅ Validación multinivel de firmas
- 🔄 Firma en lote de documentos

### 🛠️ Funcionalidades Técnicas Avanzadas
- 🔌 Soporte para múltiples tokens criptográficos
- 📜 Gestión avanzada de certificados digitales
  - Validación OCSP
  - Soporte para CRL
  - Timestamping
- 🔗 Validación completa de cadenas de certificados
- 🔍 Verificación criptográfica de hashes
- 📊 Reportes detallados de operaciones

## 🚀 Despliegue

### ⚡ Requisitos Previos
- 🐳 Docker y Docker Compose
- 🐍 Python 3.12+
- ☕ Java Runtime Environment 17+
- 💾 PostgreSQL 14.12+

### 🔧 Configuración del Entorno

1. 📥 Clonar el repositorio:
   ```bash
   git clone [URL_DEL_REPOSITORIO]
   ```

2. ⚙️ Crear archivo .env en el directorio firmar_python:
   ```bash
   cd firmar_python
   cp .env.example .env
   ```
   Configurar las siguientes variables:
   - 📊 DB_NAME: Nombre de la base de datos
   - 👤 DB_USER: Usuario de la base de datos
   - 🔑 DB_PASSWORD: Contraseña de la base de datos
   - 🌐 DB_HOST: Host de la base de datos
   - 🔌 DB_PORT: Puerto de la base de datos
   - 🔐 PRIVATE_KEY_PASSWORD: Contraseña de la clave privada
   - 📁 PRIVATE_KEY_PATH: Ruta a la clave privada
   - 📜 CERTIFICATE_PATH: Ruta al certificado

3. 📂 Configurar volúmenes en docker-compose.yml:
   - Verificar existencia de directorios montados:
     - 📁 /qnap/indice_migracion
     - 📁 /qnap/documentos_firmados
     - 📁 /var/documentos

4. 🐳 Despliegue con Docker:

   Construir las imágenes:
   ```bash
   docker-compose build
   ```

   Iniciar los servicios:
   ```bash
   docker-compose up -d
   ```

## 📚 Estructura del Proyecto

### 🔍 Sistema de Validación de Documentos
El sistema implementa validación multinivel:
- 🔐 Integridad criptográfica de documentos
- ✅ Validez temporal y estado de firmas digitales
- 🔗 Verificación completa de cadena de certificados
- 🔍 Validación de hashes con múltiples algoritmos
- 📋 Control de secuencia de trámites
- 🕒 Verificación de sellos de tiempo

### 🛡️ Sistema de Seguridad
- 🔒 Validación avanzada de certificados digitales
- 🔍 Verificación multinivel de firmas
- 📝 Registro detallado de operaciones
- 🔐 Sistema seguro de gestión de claves privadas
- 🔒 Encriptación en reposo de datos sensibles

### 📝 Sistema de Logs y Monitoreo
Logs detallados almacenados en:
- 🐍 Servicio Python: `/tmp/mod-wsgi-xxxxx/error.log`
  - Niveles: DEBUG, INFO, WARNING, ERROR
  - Rotación automática de logs
- ☕ Servicio Java: Logs estándar de Tomcat

### 🤝 Contribución
1. Fork del repositorio
2. Crear rama feature (`git checkout -b feature/NuevaCaracteristica`)
3. Commit cambios (`git commit -am 'Agrega nueva característica'`)
4. Push a la rama (`git push origin feature/NuevaCaracteristica`)
5. Crear Pull Request

### 📄 Licencia
Este proyecto es propiedad del Tribunal de Cuentas. Todos los derechos reservados.

### 🆘 Soporte
Para soporte técnico, contactar al equipo de Informática del Tribunal de Cuentas.

### 📦 Dependencias Principales

#### Servicio Python
- Flask
- PyPDF2
- cryptography
- pillow
- psycopg2
- requests
- python-dotenv

#### Servicio Java
- DSS (Digital Signature Services)
- Spring Boot
- Tomcat

### 🔄 Actualización y Mantenimiento
Para actualizar el sistema:
1. Detener los servicios
2. Actualizar el código
3. Reconstruir las imágenes
4. Reiniciar los servicios

### 🎯 Resolución de Problemas Comunes

#### 1. Error de conexión con el servicio Java
- Verificar que el servicio esté activo
- Comprobar la configuración de puertos
- Revisar logs de Java

#### 2. Problemas con la firma digital
- Validar el certificado digital
- Verificar permisos de archivos
- Comprobar conexión con el token

#### 3. Errores de base de datos
- Verificar credenciales en `.env`
- Comprobar conexión a la base de datos
- Revisar logs de PostgreSQL
