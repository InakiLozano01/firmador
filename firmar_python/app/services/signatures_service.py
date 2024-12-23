import logging
from app.utils.validation_utils import process_signature, validation_analyze
from .dss.dss_valid import validate_signature_pdf, validate_signature_json
import copy
from app.exceptions import validation_exc
import libarchive
import os
import json
import re
import unicodedata
from concurrent.futures import ThreadPoolExecutor
import base64
import hashlib
import multiprocessing
from flask import jsonify

# Configure logging
logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)

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
        logger.debug(f"SignaturesService initialized with {self.max_workers} workers")

    def init_signature_pdf(self, pdf, certificates):
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
        id_sello = pdf['id_sello']
        id_oficina = pdf['id_oficina']
        is_closing = pdf['firma_cierra']
        closing_place = pdf['firma_lugarcierre']
        id_doc = pdf['id_doc']
        is_digital = pdf['firma_digital']
        id_user = pdf['id_usuario']
        filepath = pdf['path_file']
        es_caratula = pdf.get('es_caratula', False)

        logger.debug(f"Processing PDF with ID: {id_doc}")
        logger.debug(f"Signature parameters - Field: {field_id}, Name: {name}, Area: {area}")
        logger.debug(f"Document properties - Is closing: {is_closing}, Is digital: {is_digital}, Is cover: {es_caratula}")

        app_state.current_time = int(tiempo.time() * 1000)
        app_state.datetimesigned = datetime.now().strftime("%d/%m/%Y %H:%M:%S")
        app_state.isclosing = is_closing

        if is_digital:
            try:
                logger.debug("Extracting certificate info for digital signature")
                cert_info = extract_certificate_info_name(certificates['certificate'])
                if cert_info['status'] and 'data' in cert_info and 'common_name' in cert_info['data']:
                    name = cert_info['data']['common_name']
                else:
                    raise Exception("Invalid certificate info format")
                logger.debug(f"Extracted name from certificate: {name}")
            except Exception as e:
                logger.error(f"Failed to extract certificate info: {str(e)}", exc_info=True)
                raise signature_exc.SignatureValidationError(f"Error extracting certificate info: {str(e)}")
            try:
                datetime.strptime(app_state.datetimesigned, "%d/%m/%Y %H:%M:%S")
            except ValueError:
                logger.debug("Converting datetime format")
                dt = datetime.strptime(app_state.datetimesigned, "%Y-%m-%d %H:%M:%S")
                app_state.datetimesigned = dt.strftime("%d/%m/%Y %H:%M:%S")
                logger.debug(f"Converted datetime: {app_state.datetimesigned}")
            
            try:
                logger.debug("Creating signature image")
                custom_image = create_signature_image(
                    f"{name}\n{app_state.datetimesigned}\n{stamp}\n{area}",
                    app_state.encoded_image["data"],
                    "token"
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
            
        role = name + ", " + stamp + ", " + area

        logger.debug(f"Processing signature with parameters - Digital: {is_digital}, Closing: {is_closing}")
        match (is_digital, is_closing):
            case (True, True):
                try:
                    logger.debug("Getting data to sign for digital closing signature")
                    data_to_sign_response = get_data_to_sign_token(pdf_b64, certificates, app_state.current_time, field_id, role, custom_image)
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
                    logger.debug("Getting data to sign for digital signature")
                    data_to_sign_response = get_data_to_sign_token(pdf_b64, certificates, app_state.current_time, field_id, role, custom_image)
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
                        lastpdf = get_number_and_date_then_close(signed_pdf_base64, id_doc)
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
                    'tipo_firma': tipo_firma
                }
                unlock_pdf_and_close_task(unlock_params)
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
        return id_doc, error, data_to_sign
    
    def end_signature_pdf(self, pdfs, certificates):
        logger.info("Starting PDF signature finalization")
        logger.debug(f"Input PDFs data: {json.dumps(pdfs, indent=2)}")
        logger.debug(f"Certificates data: {json.dumps(certificates, indent=2)}")
        
        # Initialize return variables
        error = None
        
        try:
            # Extract and log key parameters
            pdf_b64 = pdfs['pdf']
            field_id = pdfs['firma_lugar']
            name = pdfs['firma_nombre']
            stamp = pdfs['firma_sello']
            area = pdfs['firma_area']
            id_sello = pdfs['id_sello']
            id_oficina = pdfs['id_oficina']
            is_closing = pdfs['firma_cierra']
            closing_place = pdfs['firma_lugarcierre']
            id_doc = pdfs['id_doc']
            is_digital = pdfs['firma_digital']
            signature_value = pdfs['signatureValue']
            id_user = pdfs['id_usuario']
            filepath = pdfs['path_file']

            logger.debug(f"Processing PDF with ID: {id_doc}")
            logger.debug(f"Signature parameters - Field: {field_id}, Name: {name}, Area: {area}")
            logger.debug(f"Document properties - Is closing: {is_closing}, Is digital: {is_digital}")

            if is_digital:
                try:
                    logger.debug("Extracting certificate info for digital signature")
                    cert_info = extract_certificate_info_name(certificates['certificate'])
                    if cert_info['status'] and 'data' in cert_info and 'common_name' in cert_info['data']:
                        name = cert_info['data']['common_name']
                    else:
                        raise Exception("Invalid certificate info format")
                    logger.debug(f"Extracted name from certificate: {name}")
                except Exception as e:
                    logger.error(f"Failed to extract certificate info: {str(e)}", exc_info=True)
                    error = {"idDocFailed": id_doc, "message": f"Error al extraer nombre del certificado: {str(e)}", "stack": str(e.__traceback__)}
                    raise Exception(f"Error al extraer nombre del certificado: {str(e)}")
                try:
                    datetime.strptime(app_state.datetimesigned, "%d/%m/%Y %H:%M:%S")
                except ValueError:
                    dt = datetime.strptime(app_state.datetimesigned, "%Y-%m-%d %H:%M:%S")
                    app_state.datetimesigned = dt.strftime("%d/%m/%Y %H:%M:%S")
                try:
                    custom_image = create_signature_image(
                        f"{name}\n{app_state.datetimesigned}\n{stamp}\n{area}",
                        app_state.encoded_image["data"],
                        "token"
                    )
                    # Extract base64 string from response
                    custom_image = custom_image["data"]
                except Exception as e:
                    logger.error(f"Failed to create signature image: {str(e)}", exc_info=True)
                    error = {"idDocFailed": id_doc, "message": f"Error al crear imagen de firma: {str(e)}", "stack": str(e.__traceback__)}
                    raise Exception(f"Error al crear imagen de firma: {str(e)}")
            role = name + ", " + stamp + ", " + area

            match (is_digital, is_closing):
                case (True, True):
                    try:
                        signed_pdf_response = sign_document_token(pdf_b64, signature_value, certificates, app_state.current_time, field_id, role, custom_image)
                        if not isinstance(signed_pdf_response, dict) or 'bytes' not in signed_pdf_response:
                            raise Exception("Invalid response format from sign_document_token")
                        # Save intermediate PDF
                        save_intermediate_pdf(signed_pdf_response['bytes'], id_doc, "after_token_sign")
                    except Exception as e:
                        logger.error(f"Failed to sign document: {str(e)}", exc_info=True)
                        error = {"idDocFailed": id_doc, "message": f"Error al firmar documento: {str(e)}", "stack": str(e.__traceback__)}
                        raise Exception(f"Error al firmar documento: {str(e)}")
                    try:
                        lastpdf = get_number_and_date_then_close(signed_pdf_response['bytes'], id_doc)
                        # Save intermediate PDF
                        save_intermediate_pdf(lastpdf, id_doc, "after_number_date")
                    except Exception as e:
                        logger.error(f"Failed to close PDF: {str(e)}", exc_info=True)
                        error = {"idDocFailed": id_doc, "message": f"Error al cerrar PDF: {str(e)}", "stack": str(e.__traceback__)}
                        raise Exception(f"Error al cerrar PDF: {str(e)}")
                    try:
                        signed_pdf_base64_closed = self.sign_own_pdf(lastpdf, True, closing_place, stamp, area, name, app_state.datetimesigned, role)
                        # Save intermediate PDF
                        save_intermediate_pdf(signed_pdf_base64_closed, id_doc, "after_own_sign")
                    except Exception as e:
                        logger.error(f"Failed to add closing signature: {str(e)}", exc_info=True)
                        error = {"idDocFailed": id_doc, "message": f"Error al firmar documento: {str(e)}", "stack": str(e.__traceback__)}
                        raise Exception(f"Error al firmar documento: {str(e)}")
                    finalpdf = signed_pdf_base64_closed
                    is_closed = True

                case (True, False):
                    try:
                        signed_pdf_response = sign_document_token(pdf_b64, signature_value, certificates, app_state.current_time, field_id, role, custom_image)
                        if not isinstance(signed_pdf_response, dict) or 'bytes' not in signed_pdf_response:
                            raise Exception("Invalid response format from sign_document_token")
                        # Save intermediate PDF
                        save_intermediate_pdf(signed_pdf_response['bytes'], id_doc, "after_token_sign")
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
                    'tipo_firma': tipo_firma
                }
                unlock_pdf_and_close_task(unlock_params)
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
            
            logger.info(f"PDF signature finalization completed for document ID: {id_doc}")
            return id_doc, error
        except Exception as e:
            logger.error(f"Error in end_signature_pdf: {str(e)}", exc_info=True)
            if not error:
                error = {"idDocFailed": id_doc if 'id_doc' in locals() else None, 
                        "message": f"Error en end_signature_pdf: {str(e)}", 
                        "stack": str(e.__traceback__)}
            return None, error
    
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

            if isdigital:
                try:
                    cert_info = extract_certificate_info_name(certificates['certificate'])
                    if cert_info['status'] and 'data' in cert_info and 'common_name' in cert_info['data']:
                        name = cert_info['data']['common_name']
                    else:
                        raise Exception("Invalid certificate info format")
                except Exception as e:
                    error = {
                        "idExpFailed": f"{index['numero']}/{index['anio']}/{index['codigo']}/{index['letra']}", 
                        "message": f"Error al extraer nombre del certificado: {str(e)}",
                        "stack": str(e.__traceback__)
                    }
                    logger.error(f"Failed to extract certificate name: {str(e)}", exc_info=True)
                    return id_exp_signed, error, data_to_sign, index_signed
                    
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

            if isdigital:
                try:
                    cert_info = extract_certificate_info_name(certificates['certificate'])
                    if cert_info['status'] and 'data' in cert_info and 'common_name' in cert_info['data']:
                        name = cert_info['data']['common_name']
                    else:
                        raise Exception("Invalid certificate info format")
                except Exception as e:
                    error = ({"idExpFailed": f"{index['numero']}/{index['anio']}/{index['codigo']}/{index['letra']}", "message": "Error al extraer nombre del certificado: " + str(e)})
                    raise Exception("Error al extraer nombre del certificado: " + str(e))

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
                    custom_image = create_signature_image(f"{name}\n{datetimesigned}\n{stamp}\n{area}", encoded_image_data, "cert")
                    # Extract base64 string from response
                    custom_image = custom_image["data"]
                except Exception as e:
                    raise Exception("Error al crear imagen de firma: " + str(e))
            else:
                try:
                    # Extract base64 string from encoded_image dictionary
                    encoded_image_data = app_state.encoded_image.get("data") if isinstance(app_state.encoded_image, dict) else app_state.encoded_image
                    custom_image = create_signature_image(f"Sistema Yunga TC Tucumán\n{app_state.datetimesigned}", encoded_image_data, "yunga")
                    # Extract base64 string from response
                    custom_image = custom_image["data"]
                except Exception as e:
                    raise Exception("Error al crear imagen de firma: " + str(e))
                role = "Sistema YUNGA Tribunal de Cuentas Tucuman"

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
            # Log the custom image being used
            logger.debug(f"Using custom image (first 100 chars): {custom_image[:100]}...")
        except Exception as e:
            logger.error(f"Failed to get data to sign: {str(e)}", exc_info=True)
            raise signature_exc.SignatureProcessError(f"Error al obtener datos para firmar: {str(e)}")
        try:
            logger.debug("Getting signature value")
            data_to_sign = data_to_sign_response["bytes"]
            # Log the data to sign
            logger.debug(f"Data to sign (first 100 chars): {data_to_sign[:100]}...")
            signature_value = get_signature_value_own(data_to_sign)
            # Log the signature value
            logger.debug(f"Signature value (first 100 chars): {signature_value[:100]}...")
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
        # Log the data to sign
        logger.debug(f"JADES data to sign (first 100 chars): {data_to_sign_bytes[:100]}...")
        try:
            signature_value = get_signature_value_own(data_to_sign_bytes)
            # Log the signature value
            logger.debug(f"JADES signature value (first 100 chars): {signature_value[:100]}...")
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
