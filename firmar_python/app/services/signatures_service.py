import logging
import json
import base64
import hashlib
import io
import multiprocessing
import time as tiempo
import copy
from datetime import datetime
from datetime import timezone

from cryptography import x509
from cryptography.hazmat.backends import default_backend
from app.config.state import app_state
from app.services.dss.dss_pdf import get_data_to_sign_token, get_data_to_sign_certificate, sign_document_certificate, sign_document_token
from app.services.local_certs import get_certificate_from_local, get_signature_value_own
from app.utils.image_utils import create_sello_image as create_signature_image,create_signature_image_system
from app.utils.db import get_number_and_date_then_close, unlock_pdf_and_close_task, get_number_and_date_then_close_project, unlock_pdf_and_close_task_project
from app.utils.saving import save_signed_pdf
from app.services.dss.dss_json import get_data_to_sign_tapir_jades, sign_document_tapir_jades
from app.exceptions import signature_exc
from app.services.dss.close_pdf import close_pdf
from app.services.signing_context_store import (
    signing_context_store,
    SigningContextConflictError,
    SigningContextUnavailableError,
)
# Configure logging
logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)

def validate_certificate_expiration(certificates):
    """
    Validate that the signing certificate has not expired.

    Args:
        certificates (dict): Certificate data containing 'certificate' and 'certificateChain'

    Returns:
        tuple: (is_valid, error_message)
            is_valid (bool): True if certificate is valid, False if expired
            error_message (str): Error message if certificate is expired, None otherwise
    """
    if not certificates or not isinstance(certificates, dict):
        logger.debug("No certificates provided for validation")
        return True, None  # No certificates means no validation needed

    if 'certificate' not in certificates:
        logger.debug("No signing certificate found in certificates")
        return True, None  # No certificate means no validation needed

    try:
        # Decode the base64 certificate (DER expected)
        cert_bytes = base64.b64decode(certificates['certificate'])

        # Parse the certificate
        cert = x509.load_der_x509_certificate(cert_bytes, default_backend())

        # Prefer timezone-aware property when available to avoid deprecation warnings
        try:
            not_after = cert.not_valid_after_utc  # cryptography >= 41
        except AttributeError:
            not_after = cert.not_valid_after
            # If naive, assume UTC
            if not_after.tzinfo is None:
                not_after = not_after.replace(tzinfo=timezone.utc)

        # Current time in UTC
        current_time = datetime.now(timezone.utc)

        logger.debug(f"Certificate notAfter: {not_after}, Current time: {current_time}")

        # Check if certificate has expired (must be strictly greater than now)
        if not_after <= current_time:
            error_message = f"Certificate has expired. Expiration date: {not_after.strftime('%d/%m/%Y %H:%M:%S')}"
            logger.error(f"Certificate validation failed: {error_message}")
            return False, error_message

        logger.debug("Certificate validation successful - certificate is not expired")
        return True, None

    except Exception as e:
        error_message = f"Error validating certificate: {str(e)}"
        logger.error(f"Certificate validation error: {error_message}", exc_info=True)
        return False, error_message

# Create console handler with detailed formatting
console_handler = logging.StreamHandler()
console_handler.setLevel(logging.DEBUG)
formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
console_handler.setFormatter(formatter)
logger.addHandler(console_handler)

class SignaturesService:
    def __init__(self):
        cpu_count = multiprocessing.cpu_count()
        self.max_workers = cpu_count * 2/3  # Adjust based on testing
        self.signing_context_store = signing_context_store
        logger.debug(f"SignaturesService initialized with {self.max_workers} workers")

    @staticmethod
    def generate_batch_id(pdfs):
        doc_ids = [str(pdf.get("id_doc")) for pdf in pdfs if pdf.get("id_doc")]
        first_user = "unknown"
        for pdf in pdfs:
            if pdf.get("id_usuario") is not None:
                first_user = str(pdf.get("id_usuario"))
                break
        return signing_context_store.generate_batch_id(doc_ids, first_user)

    def signature_pdf_loro(self, pdf):
        logger.info("Starting PDF signature initialization for loro")

        error = None

        pdf_b64 = pdf['pdf']
        field_id = pdf['firma_lugar']
        id_doc = pdf['id_doc']
        fields_to_fill = pdf['fields_to_fill']

        logger.debug(f"Processing PDF with ID: {id_doc}")
        logger.debug(f"Signature parameters - Field: {field_id}, Fields to fill: {fields_to_fill}")
        
        # Use the enhanced app_state methods to generate and store a timestamp for this document
        document_timestamp = app_state.set_document_timestamp(id_doc)

        app_state.current_time = document_timestamp
        app_state.datetimesigned = datetime.now().strftime("%d/%m/%Y %H:%M:%S")

        app_state.set_document_data(id_doc, 'datetimesigned', app_state.datetimesigned)

        logger.debug(f"Set app_state.current_time to {app_state.current_time} for document {id_doc}")
        logger.debug(f"Set app_state.datetimesigned to {app_state.datetimesigned} for document {id_doc}")

        try:
            datetime.strptime(app_state.datetimesigned, "%d/%m/%Y %H:%M:%S")
        except ValueError:
            logger.debug("Converting datetime format")
            dt = datetime.strptime(app_state.datetimesigned, "%Y-%m-%d %H:%M:%S")
            app_state.datetimesigned = dt.strftime("%d/%m/%Y %H:%M:%S")
            # Update the document-specific data too
            app_state.set_document_data(id_doc, 'datetimesigned', app_state.datetimesigned)
            logger.debug(f"Converted datetime: {app_state.datetimesigned}")

        try:
            # Extract base64 string from encoded_image dictionary
            encoded_image_data = app_state.encoded_image_yunga.get("data") if isinstance(app_state.encoded_image_yunga, dict) else app_state.encoded_image_yunga
            custom_image = create_signature_image_system(f"TRIBUNAL DE CUENTAS TUCUMÁN\n{app_state.datetimesigned}", encoded_image_data, "yunga",usuario="SISTEMA YUNGA")
            # Extract base64 string from response
            custom_image = custom_image["data"]
        except Exception as e:
            logger.error(f"Failed to create signature image: {str(e)}", exc_info=True)
            error = ({"idDocFailed": id_doc, "message": f"Error al crear imagen de firma: {str(e)}"})
            raise signature_exc.SignatureValidationError(f"Error al crear imagen de firma: {str(e)}")
        
        role = "TAPIR - Gestor de documentos y expedientes digitales"
        
        try:
            pdf_b64_filled = close_pdf(pdf_b64, fields_to_fill)
        except Exception as e:
            logger.error(f"Failed to close PDF: {str(e)}", exc_info=True)
            error = ({"idDocFailed": id_doc, "message": f"Error al cerrar PDF: {str(e)}"})
            raise signature_exc.SignatureValidationError(f"Error al cerrar PDF: {str(e)}")

        logger.debug("Getting data to sign for digital signature using timestamp {document_timestamp}")
        try:
            certificates = get_certificate_from_local()
        except Exception as e:
            raise Exception("Error al obtener certificado local: " + str(e))
        try:
            signed_pdf_base64 = self.create_and_sign(pdf_b64_filled, certificates, field_id, role, custom_image)
        except Exception as e:
            raise Exception("Error al firmar documento: " + str(e))

        return id_doc, error, signed_pdf_base64
        
    def init_signature_pdf(self, pdf, certificates, batch_id=None):
        logger.info("Starting PDF signature initialization")
        logger.debug(f"Input PDF data: {json.dumps(pdf, indent=2)}")
        logger.debug(f"Certificates data: {json.dumps(certificates, indent=2)}")
        
        # Initialize return variables
        error = None
        data_to_sign = None
        
        # Extract and log key parameters
        pdf_b64 = pdf['pdf']
        field_id = pdf['firma_lugar']
        name = pdf['firma_nombre']
        stamp = pdf['firma_sello']
        area = pdf['firma_area']
        cuil = pdf['firma_cuil']
        id_sello = pdf['id_sello']
        id_oficina = pdf['id_oficina']
        is_closing = pdf['firma_cierra']
        closing_place = pdf['firma_lugarcierre']
        id_doc = pdf['id_doc']
        is_digital = pdf['firma_digital']
        id_user = pdf['id_usuario']
        filepath = pdf['path_file']
        es_caratula = pdf.get('es_caratula', False)
        is_project = pdf.get('is_project', False)

        logger.debug(f"Processing PDF with ID: {id_doc}")
        logger.debug(f"Signature parameters - Field: {field_id}, Name: {name}, Area: {area}")
        logger.debug(f"Document properties - Is closing: {is_closing}, Is digital: {is_digital}, Is cover: {es_caratula}")

        document_timestamp = int(tiempo.time() * 1000)
        document_datetimesigned = datetime.now().strftime("%d/%m/%Y %H:%M:%S")

        try:
            # Validate certificate expiration if certificates are provided
            if certificates:
                logger.debug("Validating certificate expiration")
                is_valid, cert_error = validate_certificate_expiration(certificates)
                if not is_valid:
                    logger.error(f"Certificate validation failed for document {id_doc}: {cert_error}")
                    error = ({"idDocFailed": id_doc, "message": f"Error de validación de certificado: {cert_error}"})
                    raise signature_exc.SignatureValidationError(f"Error de validación de certificado: {cert_error}")
        except Exception as e:
            logger.error(f"Error validating certificate expiration: {str(e)}", exc_info=True)
            error = ({"idDocFailed": id_doc, "message": f"Error al validar certificado: {str(e)}"})
            raise signature_exc.SignatureValidationError(f"Error al validar certificado: {str(e)}")

        if is_digital:
            try:
                current_batch_id = batch_id or self.generate_batch_id([pdf])
                context, context_result = self.signing_context_store.create_or_get_init_context(
                    batch_id=current_batch_id,
                    id_doc=str(id_doc),
                    id_user=str(id_user),
                    field_id=str(field_id),
                    is_closing=bool(is_closing),
                    is_digital=bool(is_digital),
                    pdf_b64=pdf_b64,
                )
                document_timestamp = int(context["timestamp_ms"])
                document_datetimesigned = context["datetimesigned"]
                logger.info(
                    "signing_context_init "
                    f"context_source=redis context_result={context_result} "
                    f"id_doc={id_doc} batch_id={context.get('batch_id')} "
                    f"timestamp_init={document_timestamp}"
                )
            except SigningContextConflictError as conflict_exc:
                error = {
                    "idDocFailed": id_doc,
                    "message": "Error de contexto pendiente: existe una firma en curso para este documento.",
                    "details": str(conflict_exc),
                }
                logger.warning(
                    "signing_context_init "
                    f"context_source=redis context_result=conflict id_doc={id_doc} "
                    f"batch_id={batch_id} error={conflict_exc}"
                )
                return id_doc, error, data_to_sign
            except SigningContextUnavailableError as unavailable_exc:
                error = {
                    "idDocFailed": id_doc,
                    "message": f"Error de infraestructura al guardar contexto de firma: {unavailable_exc}",
                }
                logger.error(
                    "signing_context_init "
                    f"context_source=redis context_result=error id_doc={id_doc} "
                    f"batch_id={batch_id} error={unavailable_exc}"
                )
                return id_doc, error, data_to_sign

        # Keep compatibility with methods that still use app_state values directly.
        app_state.current_time = document_timestamp
        app_state.datetimesigned = document_datetimesigned
        app_state.isclosing = is_closing

        logger.debug(f"Set app_state.current_time to {app_state.current_time} for document {id_doc}")
        logger.debug(f"Set app_state.datetimesigned to {app_state.datetimesigned} for document {id_doc}")
        logger.debug(f"Set app_state.isclosing to {app_state.isclosing} for document {id_doc}")

        if is_digital:
            try:
                datetime.strptime(app_state.datetimesigned, "%d/%m/%Y %H:%M:%S")
            except ValueError:
                logger.debug("Converting datetime format")
                dt = datetime.strptime(app_state.datetimesigned, "%Y-%m-%d %H:%M:%S")
                app_state.datetimesigned = dt.strftime("%d/%m/%Y %H:%M:%S")
                logger.debug(f"Converted datetime: {app_state.datetimesigned}")
            
            try:
                logger.debug("Creating signature image")
                # For projects, exclude area from signature image
                signature_text = f"{stamp}\n{app_state.datetimesigned}" if is_project else f"{stamp}\n{area}\n{app_state.datetimesigned}"
                custom_image = create_signature_image(signature_text, app_state.encoded_image["data"], "cert",
                usuario=f"{name}",
                label_signed_by= "Firmado digitalmente por"
                )
                # Extract base64 string from response
                custom_image = custom_image["data"]
                logger.debug("Signature image created successfully")
                # Log the image data
                logger.debug(f"Generated signature image (first 100 chars): {custom_image[:100]}...")
            except Exception as e:
                logger.error(f"Failed to create signature image: {str(e)}", exc_info=True)
                error = ({"idDocFailed": id_doc, "message": f"Error al crear imagen de firma: {str(e)}"})
                raise signature_exc.SignatureValidationError(f"Error al crear imagen de firma: {str(e)}")
            
        role = name + (", CUIL " + cuil if cuil else "") + ", " + stamp + ", " + area

        logger.debug(f"Processing signature with parameters - Digital: {is_digital}, Closing: {is_closing}")
        match (is_digital, is_closing):
            case (True, True):
                try:
                    logger.debug(f"Getting data to sign for digital closing signature using timestamp {document_timestamp}")
                    data_to_sign_response = get_data_to_sign_token(pdf_b64, certificates, document_timestamp, field_id, role, custom_image)
                    data_to_sign = (data_to_sign_response["bytes"])
                    logger.debug("Successfully obtained data to sign")
                    # Log the data to sign
                    logger.debug(f"Data to sign (first 100 chars): {data_to_sign[:100]}...")
                except Exception as e:
                    logger.error(f"Failed to get data to sign for digital closing signature: {str(e)}", exc_info=True)
                    error = ({"idDocFailed": id_doc, "message": f"Error al obtener datos para firmar: {str(e)}"})
                    raise signature_exc.SignatureValidationError(f"Error al obtener datos para firmar: {str(e)}")
            case (True, False):
                try:
                    logger.debug(f"Getting data to sign for digital signature using timestamp {document_timestamp}")
                    data_to_sign_response = get_data_to_sign_token(pdf_b64, certificates, document_timestamp, field_id, role, custom_image)
                    data_to_sign = (data_to_sign_response["bytes"])
                    logger.debug("Successfully obtained data to sign")
                    # Log the data to sign
                    logger.debug(f"Data to sign (first 100 chars): {data_to_sign[:100]}...")
                except Exception as e:
                    logger.error(f"Failed to get data to sign for digital signature: {str(e)}", exc_info=True)
                    error = ({"idDocFailed": id_doc, "message": f"Error al obtener datos para firmar: {str(e)}"})
                    raise signature_exc.SignatureValidationError(f"Error al obtener datos para firmar: {str(e)}")
            case (False, True):
                try:
                    logger.debug("Processing non-digital closing signature")
                    signed_pdf_base64 = self.sign_own_pdf(pdf_b64, False, field_id, stamp, area, name, app_state.datetimesigned, role)
                    logger.debug("Successfully signed PDF")
                except Exception as e:
                    logger.error(f"Failed to sign PDF with non-digital closing signature: {str(e)}", exc_info=True)
                    error = ({"idDocFailed": id_doc, "message": f"Error al firmar documento: {str(e)}"})
                    raise signature_exc.SignatureValidationError(f"Error al firmar documento: {str(e)}")
                if not es_caratula:
                    try:
                        logger.debug("Getting number and date for non-cover PDF")
                        if not is_project:
                            lastpdf = get_number_and_date_then_close(signed_pdf_base64, id_doc)
                        else:
                            lastpdf = get_number_and_date_then_close_project(signed_pdf_base64, id_doc)
                        logger.debug("Successfully obtained number and date")
                    except Exception as e:
                        logger.error(f"Failed to close PDF: {str(e)}", exc_info=True)
                        error = ({"idDocFailed": id_doc, "message": f"Error al cerrar PDF: {str(e)}"})
                        raise signature_exc.SignatureValidationError(f"Error al cerrar PDF: {str(e)}")
                else:
                    logger.debug("Skipping number and date for cover page")
                    lastpdf = signed_pdf_base64
                try:
                    logger.debug("Signing PDF with closing signature")
                    signed_pdf_base64_closed = self.sign_own_pdf(lastpdf, True, closing_place, stamp, area, name, app_state.datetimesigned, role)
                    logger.debug("Successfully added closing signature")
                except Exception as e:
                    logger.error(f"Failed to add closing signature: {str(e)}", exc_info=True)
                    error = ({"idDocFailed": id_doc, "message": f"Error al firmar documento: {str(e)}"})
                    raise signature_exc.SignatureValidationError(f"Error al firmar documento: {str(e)}")
                finalpdf = signed_pdf_base64_closed
                is_closed = True
                logger.debug("PDF closing process completed")

            case (False, False):
                try:
                    logger.debug("Processing non-digital signature")
                    signed_pdf_base64 = self.sign_own_pdf(pdf_b64, False, field_id, stamp, area, name, app_state.datetimesigned, role)
                    logger.debug("Successfully signed PDF")
                except Exception as e:
                    logger.error(f"Failed to sign PDF with non-digital signature: {str(e)}", exc_info=True)
                    error = ({"idDocFailed": id_doc, "message": f"Error al firmar documento: {str(e)}"})
                    raise signature_exc.SignatureValidationError(f"Error al firmar documento: {str(e)}")
                finalpdf = signed_pdf_base64
                is_closed = False
                logger.debug("Non-digital signature process completed")

        tipo_firma = 2 if is_digital else 1
        logger.debug(f"Signature type set to: {tipo_firma}")

        if not is_digital:
            logger.debug("Processing hash for non-digital signature")
            hash_object = hashlib.sha256(io.BytesIO(base64.b64decode(finalpdf)).getvalue())
            hash_doc = hash_object.hexdigest()
            logger.debug("Hash generated successfully")

            try:
                logger.debug("Unlocking PDF and closing task")
                unlock_params = {
                    'id_doc': id_doc,
                    'id_user': id_user,
                    'hash_doc': hash_doc,
                    'is_closed': is_closed,
                    'id_sello': id_sello,
                    'id_oficina': id_oficina,
                    'tipo_firma': tipo_firma,
                    'is_signed': 1  # Explicitly set is_signed to 1 for successful signatures
                }
                if not is_project:
                    unlock_pdf_and_close_task(unlock_params)
                else:
                    unlock_pdf_and_close_task_project(unlock_params)
                logger.debug("Successfully unlocked PDF and closed task")
            except Exception as e:
                logger.error(f"Failed to unlock PDF and close task: {str(e)}", exc_info=True)
                error = ({"idDocFailed": id_doc, "message": "Error al desbloquear PDF: " + str(e)})
                raise Exception("Error al desbloquear PDF: " + str(e))
            try:
                logger.debug(f"Saving signed PDF to filepath: {filepath}")
                save_signed_pdf(finalpdf, filepath)
                logger.debug("Successfully saved signed PDF")
            except Exception as e:
                logger.error(f"Failed to save signed PDF: {str(e)}", exc_info=True)
                error = ({"idDocFailed": id_doc, "message": f"Error al guardar PDF firmado: {str(e)}"})
                raise signature_exc.SignatureValidationError(f"Error al guardar PDF firmado: {str(e)}")

        logger.info(f"PDF signature initialization completed for document ID: {id_doc}")
        # Log that we're using the document-specific timestamp
        logger.debug(f"Using document timestamp {document_timestamp} for data_to_sign generation")
        return id_doc, error, data_to_sign
    
    def end_signature_pdf(self, pdfs, certificates):
        logger.info("Starting PDF signature finalization")
        logger.debug(f"Input PDFs data: {json.dumps(pdfs, indent=2)}")
        logger.debug(f"Certificates data: {json.dumps(certificates, indent=2)}")
        
        # Initialize return variables
        error = None
        id_doc = pdfs.get('id_doc', 'unknown') if isinstance(pdfs, dict) else 'unknown'
        old_current_time = app_state.current_time
        old_datetimesigned = app_state.datetimesigned
        old_isclosing = app_state.isclosing
        
        try:
            # Validate certificate expiration first if certificates provided
            id_doc_preview = pdfs.get('id_doc') if isinstance(pdfs, dict) else None
            if certificates:
                logger.debug("Validating certificate expiration before finalization")
                is_valid, cert_error = validate_certificate_expiration(certificates)
                if not is_valid:
                    logger.error(f"Certificate validation failed for document {id_doc_preview}: {cert_error}")
                    error = {"idDocFailed": id_doc_preview, "message": f"Error de validación de certificado: {cert_error}"}
                    raise signature_exc.SignatureValidationError(f"Error de validación de certificado: {cert_error}")

            # Extract and log key parameters
            pdf_b64 = pdfs['pdf']
            field_id = pdfs['firma_lugar']
            name = pdfs['firma_nombre']
            stamp = pdfs['firma_sello']
            area = pdfs['firma_area']
            cuil = pdfs['firma_cuil']
            id_sello = pdfs['id_sello']
            id_oficina = pdfs['id_oficina']
            is_closing = pdfs['firma_cierra']
            closing_place = pdfs['firma_lugarcierre']
            id_doc = pdfs['id_doc']
            is_digital = pdfs['firma_digital']
            signature_value = pdfs['signatureValue']
            id_user = pdfs['id_usuario']
            filepath = pdfs['path_file']
            is_project = pdfs['is_project'] if 'is_project' in pdfs else False

            if is_digital:
                try:
                    context = self.signing_context_store.get_context_for_end(str(id_doc))
                except SigningContextUnavailableError as unavailable_exc:
                    error = {
                        "idDocFailed": id_doc,
                        "message": f"Error de infraestructura al leer contexto de firma: {unavailable_exc}"
                    }
                    logger.error(
                        "signing_context_end "
                        f"context_source=redis context_result=error id_doc={id_doc} "
                        f"error={unavailable_exc}"
                    )
                    return id_doc, error

                if not context:
                    error = {
                        "idDocFailed": id_doc,
                        "message": "No se encontró contexto de firma pendiente para el documento (expirado o inexistente)."
                    }
                    logger.warning(
                        "signing_context_end "
                        f"context_source=redis context_result=miss id_doc={id_doc}"
                    )
                    return id_doc, error

                expected_pdf_sha256 = self.signing_context_store.build_pdf_sha256(pdf_b64)
                expected_fingerprint = self.signing_context_store.build_request_fingerprint(
                    id_doc=str(id_doc),
                    id_user=str(id_user),
                    field_id=str(field_id),
                    is_closing=bool(is_closing),
                    is_digital=bool(is_digital),
                    pdf_sha256=expected_pdf_sha256,
                )

                mismatch_reasons = []
                if str(context.get("id_user")) != str(id_user):
                    mismatch_reasons.append("id_user")
                if str(context.get("field_id")) != str(field_id):
                    mismatch_reasons.append("field_id")
                if str(context.get("pdf_sha256")) != expected_pdf_sha256:
                    mismatch_reasons.append("pdf_sha256")
                if str(context.get("request_fingerprint")) != expected_fingerprint:
                    mismatch_reasons.append("request_fingerprint")

                if mismatch_reasons:
                    error = {
                        "idDocFailed": id_doc,
                        "message": f"Contexto de firma inválido para el documento. Campos inconsistentes: {', '.join(mismatch_reasons)}."
                    }
                    logger.warning(
                        "signing_context_end "
                        f"context_source=redis context_result=mismatch id_doc={id_doc} "
                        f"batch_id={context.get('batch_id')} mismatch={mismatch_reasons}"
                    )
                    return id_doc, error

                document_timestamp = int(context["timestamp_ms"])
                doc_datetimesigned = context["datetimesigned"]
                doc_isclosing = context.get("isclosing", is_closing)
                logger.info(
                    "signing_context_end "
                    f"context_source=redis context_result=hit id_doc={id_doc} "
                    f"batch_id={context.get('batch_id')} timestamp_end={document_timestamp}"
                )
            else:
                document_timestamp = int(tiempo.time() * 1000)
                doc_datetimesigned = datetime.now().strftime("%d/%m/%Y %H:%M:%S")
                doc_isclosing = is_closing

            # Temporarily set app_state values to this document's values for compatibility
            # with existing code that uses app_state directly
            app_state.current_time = document_timestamp
            app_state.datetimesigned = doc_datetimesigned
            app_state.isclosing = doc_isclosing

            logger.debug(f"Processing PDF with ID: {id_doc}")
            logger.debug(f"Signature parameters - Field: {field_id}, Name: {name}, Area: {area}")
            logger.debug(f"Document properties - Is closing: {is_closing}, Is digital: {is_digital}")

            if is_digital:
                try:
                    datetime.strptime(app_state.datetimesigned, "%d/%m/%Y %H:%M:%S")
                except ValueError:
                    dt = datetime.strptime(app_state.datetimesigned, "%Y-%m-%d %H:%M:%S")
                    app_state.datetimesigned = dt.strftime("%d/%m/%Y %H:%M:%S")
                try:
                    # For projects, exclude area from signature image
                    signature_text = f"{stamp}\n{app_state.datetimesigned}" if is_project else f"{stamp}\n{area}\n{app_state.datetimesigned}"
                    custom_image = create_signature_image(signature_text, app_state.encoded_image["data"], "token",
                    usuario=f"{name}",
                    label_signed_by= "Firmado digitalmente por"
                    )
                    # Extract base64 string from response
                    custom_image = custom_image["data"]
                except Exception as e:
                    logger.error(f"Failed to create signature image: {str(e)}", exc_info=True)
                    error = {"idDocFailed": id_doc, "message": f"Error al crear imagen de firma: {str(e)}", "stack": str(e.__traceback__)}
                    raise Exception(f"Error al crear imagen de firma: {str(e)}")
            role = name + (", CUIL " + cuil if cuil else "") + ", " + stamp + ", " + area

            match (is_digital, is_closing):
                case (True, True):
                    try:
                        # Use document_timestamp instead of app_state.current_time
                        signed_pdf_response = sign_document_token(pdf_b64, signature_value, certificates, document_timestamp, field_id, role, custom_image)
                        if not isinstance(signed_pdf_response, dict) or 'bytes' not in signed_pdf_response:
                            raise Exception("Invalid response format from sign_document_token")
                    except Exception as e:
                        logger.error(f"Failed to sign document: {str(e)}", exc_info=True)
                        error = {"idDocFailed": id_doc, "message": f"Error al firmar documento: {str(e)}", "stack": str(e.__traceback__)}
                        raise Exception(f"Error al firmar documento: {str(e)}")
                    try:
                        if not is_project:
                            lastpdf = get_number_and_date_then_close(signed_pdf_response['bytes'], id_doc)
                        else:
                            lastpdf = get_number_and_date_then_close_project(signed_pdf_response['bytes'], id_doc)
                    except Exception as e:
                        logger.error(f"Failed to close PDF: {str(e)}", exc_info=True)
                        error = {"idDocFailed": id_doc, "message": f"Error al cerrar PDF: {str(e)}", "stack": str(e.__traceback__)}
                        raise Exception(f"Error al cerrar PDF: {str(e)}")
                    try:
                        signed_pdf_base64_closed = self.sign_own_pdf(lastpdf, True, closing_place, stamp, area, name, app_state.datetimesigned, role)
                    except Exception as e:
                        logger.error(f"Failed to add closing signature: {str(e)}", exc_info=True)
                        error = {"idDocFailed": id_doc, "message": f"Error al firmar documento: {str(e)}", "stack": str(e.__traceback__)}
                        raise Exception(f"Error al firmar documento: {str(e)}")
                    finalpdf = signed_pdf_base64_closed
                    is_closed = True

                case (True, False):
                    try:
                        # Use document_timestamp instead of app_state.current_time
                        signed_pdf_response = sign_document_token(pdf_b64, signature_value, certificates, document_timestamp, field_id, role, custom_image)
                        if not isinstance(signed_pdf_response, dict) or 'bytes' not in signed_pdf_response:
                            raise Exception("Invalid response format from sign_document_token")
                    except Exception as e:
                        logger.error(f"Failed to sign document: {str(e)}", exc_info=True)
                        error = {"idDocFailed": id_doc, "message": f"Error al firmar documento: {str(e)}", "stack": str(e.__traceback__)}
                        raise Exception(f"Error al firmar documento: {str(e)}")
                    finalpdf = signed_pdf_response['bytes']
                    is_closed = False
            
            hash_object = hashlib.sha256(io.BytesIO(base64.b64decode(finalpdf)).getvalue())
            hash_doc = hash_object.hexdigest()

            tipo_firma = 2 if is_digital else 1

            try:
                unlock_params = {
                    'id_doc': id_doc,
                    'id_user': id_user,
                    'hash_doc': hash_doc,
                    'is_closed': is_closed,
                    'id_sello': id_sello,
                    'id_oficina': id_oficina,
                    'tipo_firma': tipo_firma,
                    'is_signed': 1  # Explicitly set is_signed to 1 for successful signatures
                }
                if not is_project:
                    unlock_pdf_and_close_task(unlock_params)
                else:
                    unlock_pdf_and_close_task_project(unlock_params)
            except Exception as e:
                logger.error(f"Failed to unlock PDF and close task: {str(e)}", exc_info=True)
                error = {"idDocFailed": id_doc, "message": f"Error al desbloquear PDF: {str(e)}", "stack": str(e.__traceback__)}
                raise Exception(f"Error al desbloquear PDF: {str(e)}")
            try:
                logger.debug(f"Saving signed PDF to filepath: {filepath}")
                save_signed_pdf(finalpdf, filepath)
                logger.debug("Successfully saved signed PDF")
            except Exception as e:
                logger.error(f"Failed to save signed PDF: {str(e)}", exc_info=True)
                error = {"idDocFailed": id_doc, "message": f"Error al guardar PDF firmado: {str(e)}", "stack": str(e.__traceback__)}
                raise Exception(f"Error al guardar PDF firmado: {str(e)}")

            if is_digital:
                try:
                    self.signing_context_store.delete_context(str(id_doc))
                    logger.info(
                        "signing_context_end "
                        f"context_source=redis context_result=deleted id_doc={id_doc}"
                    )
                except SigningContextUnavailableError as delete_exc:
                    logger.warning(
                        "signing_context_end "
                        f"context_source=redis context_result=delete_error id_doc={id_doc} "
                        f"error={delete_exc}"
                    )
            
            logger.info(f"PDF signature finalization completed for document ID: {id_doc}")
            return id_doc, error
        except Exception as e:
            logger.error(f"Error during signature finalization: {str(e)}", exc_info=True)
            if error is None:
                error = {"idDocFailed": id_doc, "message": f"Error al finalizar firma: {str(e)}", "stack": str(e.__traceback__)}
            return id_doc, error
        finally:
            # Restore previous app_state values even when any doc fails.
            app_state.current_time = old_current_time
            app_state.datetimesigned = old_datetimesigned
            app_state.isclosing = old_isclosing
    
    def init_sign_jades(self, index_data, certificates, data_signature):
        """
        Initialize JADES signature process.
        
        Args:
            index_data: Index data to sign
            certificates: Certificate data
            data_signature: Signature metadata
            
        Returns:
            tuple: (id_exp_signed, error, data_to_sign, index_signed)
        """
        logger.info("Starting JADES signature initialization")
        
        # Initialize return variables
        id_exp_signed = None
        error = None
        data_to_sign = None
        index_signed = None
        
        try:
            index = index_data['index']
            jsonb64 = copy.deepcopy(index)
            index = json.loads(base64.b64decode(jsonb64).decode('utf-8'))

            tramites = index['tramites']

            name = data_signature['name']
            stamp = data_signature['stamp']
            area = data_signature['area']
            isdigital = data_signature['isdigital']

            tramite = tramites[-1]

            role = name + ", " + stamp + ", " + area

            if isdigital:
                try:
                    data_to_sign_response = get_data_to_sign_tapir_jades(jsonb64, certificates, app_state.current_time, role)
                    data_to_sign = data_to_sign_response["bytes"]
                except Exception as e:
                    error = {
                        "idExpFailed": f"{index['numero']}/{index['anio']}/{index['codigo']}/{index['letra']}", 
                        "message": f"Error al obtener datos para firmar: {str(e)}",
                        "stack": str(e.__traceback__)
                    }
                    logger.error(f"Failed to get data to sign: {str(e)}", exc_info=True)
                    return id_exp_signed, error, data_to_sign, index_signed
            else:
                try:
                    signed_json_b64 = self.sign_own_jades(jsonb64, role)
                except Exception as e:
                    error = {
                        "idExpFailed": f"{index['numero']}/{index['anio']}/{index['codigo']}/{index['letra']}", 
                        "message": f"Error al firmar documento: {str(e)}",
                        "stack": str(e.__traceback__)
                    }
                    logger.error(f"Failed to sign document: {str(e)}", exc_info=True)
                    return id_exp_signed, error, data_to_sign, index_signed
                    
                tramite['firma'] = signed_json_b64

            if not isdigital:
                id_exp_signed = f"{index['numero']}/{index['anio']}/{index['codigo']}/{index['letra']}"
                index_signed = index

            logger.info("JADES signature initialization completed successfully")
            return id_exp_signed, error, data_to_sign, index_signed
            
        except Exception as e:
            error = {
                "idExpFailed": f"{index['numero']}/{index['anio']}/{index['codigo']}/{index['letra']}" if 'index' in locals() else "unknown",
                "message": f"Error inesperado en init_sign_jades: {str(e)}",
                "stack": str(e.__traceback__)
            }
            logger.error(f"Unexpected error in init_sign_jades: {str(e)}", exc_info=True)
            return id_exp_signed, error, data_to_sign, index_signed
    
    def end_sign_jades(self, index_data, certificates, data_signature):
        try:
            index = index_data['index']
            jsonb64 = copy.deepcopy(index)
            index = json.loads(base64.b64decode(jsonb64).decode('utf-8'))

            tramites = index['tramites']

            name = data_signature['name']
            stamp = data_signature['stamp']
            area = data_signature['area']
            isdigital = data_signature['isdigital']

            tramite = tramites[-1]
            signature = index_data['signature']

            role = name + ", " + stamp + ", " + area

            if isdigital:
                try:
                    signed_json_response = sign_document_tapir_jades(jsonb64, signature, certificates, app_state.current_time, role)
                except Exception as e:
                    error = ({"idExpFailed": f"{index['numero']}/{index['anio']}/{index['codigo']}/{index['letra']}", "message": "Error al firmar documento: " + str(e)})
                    raise Exception("Error al firmar documento: " + str(e))
                signed_json_b64 = signed_json_response['bytes']
                tramite['firma'] = signed_json_b64

            id_exp_signed = (f"{index['numero']}/{index['anio']}/{index['codigo']}/{index['letra']}")
            index_signed = index

        except Exception as e:
            pass
        return id_exp_signed, error, index_signed

    def sign_own_pdf(self, pdf, is_yunga_sign, field_to_sign, stamp, area, name, datetimesigned, role):
        """
        Firma el PDF con certificado propio del servidor.

        Args:
            pdf (str): Base64 encoded PDF to sign.
            is_yunga_sign (bool): Flag indicating if it's a Yunga sign.
            field_to_sign (str): Field to sign.
            stamp (str): Stamp information.
            area (str): Area information.
            name (str): Name of the signer.
            datetimesigned (str): Datetime of the signature.

        Returns:
            str: Base64 encoded signed PDF.
            int: HTTP status code.
        """
        try:
            # Convert from Y-m-d to d/m/Y format
            try:
                datetime.strptime(datetimesigned, "%d/%m/%Y %H:%M:%S")
            except ValueError:
                dt = datetime.strptime(datetimesigned, "%Y-%m-%d %H:%M:%S") 
                app_state.datetimesigned = dt.strftime("%d/%m/%Y %H:%M:%S")
            if not is_yunga_sign:
                try:
                    # Extract base64 string from encoded_image dictionary
                    encoded_image_data = app_state.encoded_image.get("data") if isinstance(app_state.encoded_image, dict) else app_state.encoded_image
                    custom_image = create_signature_image(f"{stamp}\n{area}\n{datetimesigned}", encoded_image_data, "cert",
                    usuario=f"{name}",
                    label_signed_by= "Firmado electrónicamente por"
                    )
                    # Extract base64 string from response
                    custom_image = custom_image["data"]
                except Exception as e:
                    raise Exception("Error al crear imagen de firma: " + str(e))
            else:
                try:
                    # Extract base64 string from encoded_image dictionary
                    encoded_image_data = app_state.encoded_image_yunga.get("data") if isinstance(app_state.encoded_image_yunga, dict) else app_state.encoded_image_yunga
                    custom_image = create_signature_image_system(f"TRIBUNAL DE CUENTAS TUCUMÁN\n{app_state.datetimesigned}", encoded_image_data, "yunga",usuario="SISTEMA YUNGA")
                    # Extract base64 string from response
                    custom_image = custom_image["data"]
                except Exception as e:
                    raise Exception("Error al crear imagen de firma: " + str(e))
                role = "TAPIR - Gestor de documentos y expedientes digitales"

            try:
                certificates = get_certificate_from_local()
            except Exception as e:
                raise Exception("Error al obtener certificado local: " + str(e))
            try:
                signed_pdf_base64 = self.create_and_sign(pdf, certificates, field_to_sign, role, custom_image)
            except Exception as e:
                raise Exception("Error al firmar documento: " + str(e))

            return signed_pdf_base64
        except Exception as e:
            raise Exception("Error en sign_own_pdf: " + str(e))
        
    @staticmethod
    def create_and_sign(pdf, certificates, field_to_sign, role, custom_image):
        try:
            logger.debug("Getting data to sign")
            data_to_sign_response = get_data_to_sign_certificate(pdf, certificates, app_state.current_time, field_to_sign, role, custom_image)
        except Exception as e:
            logger.error(f"Failed to get data to sign: {str(e)}", exc_info=True)
            raise signature_exc.SignatureProcessError(f"Error al obtener datos para firmar: {str(e)}")
        try:
            logger.debug("Getting signature value")
            data_to_sign = data_to_sign_response["bytes"]
            signature_value = get_signature_value_own(data_to_sign)
        except Exception as e:
            logger.error(f"Failed to get signature value: {str(e)}", exc_info=True)
            raise signature_exc.SignatureProcessError(f"Error al obtener valor de firma: {str(e)}")
        try:
            logger.debug("Signing document")
            signed_pdf_response = sign_document_certificate(pdf, signature_value, certificates, app_state.current_time, field_to_sign, role, custom_image)
        except Exception as e:
            logger.error(f"Failed to sign document: {str(e)}", exc_info=True)
            raise signature_exc.SignatureProcessError(f"Error al firmar documento: {str(e)}")
        
        logger.debug("Document signed successfully")
        return signed_pdf_response['bytes']
    
    def sign_own_jades(self, json, role):
        """
        Sign a JADES document using the own signature method.
        """
        try:
            # Ensure current_time is set
            app_state.current_time = int(tiempo.time() * 1000)
            app_state.datetimesigned = datetime.now().strftime("%d/%m/%Y %H:%M:%S")
            
            certificates = get_certificate_from_local()
            logger.debug("Local certificates obtained successfully")
        except Exception as e:
            logger.error(f"Failed to get local certificate: {str(e)}", exc_info=True)
            raise Exception("Error al obtener certificado local: " + str(e))
        try:
            data_to_sign_response = get_data_to_sign_tapir_jades(json, certificates, app_state.current_time, role)
            logger.debug("Successfully obtained data to sign for JADES")
        except Exception as e:
            logger.error(f"Failed to get data to sign for JADES: {str(e)}", exc_info=True)
            raise Exception("Error al obtener datos para firmar: " + str(e))
        data_to_sign_bytes = data_to_sign_response["bytes"]
        try:
            signature_value = get_signature_value_own(data_to_sign_bytes)
        except Exception as e:
            logger.error(f"Failed to get signature value for JADES: {str(e)}", exc_info=True)
            raise Exception("Error al obtener valor de firma: " + str(e))
        try:
            signed_json_response = sign_document_tapir_jades(json, signature_value, certificates, app_state.current_time, role)
            logger.debug("JADES document signed successfully")
        except Exception as e:
            logger.error(f"Failed to sign JADES document: {str(e)}", exc_info=True)
            raise Exception("Error al firmar documento: " + str(e))
        return signed_json_response['bytes']
