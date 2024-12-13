import copy
import json

from flask import jsonify
from app.config.state import app_state
from datetime import datetime
import time as tiempo
import base64
import hashlib
import io
from app.utils.certificates_utils import extract_certificate_info_name
from app.services.dss.dss_pdf import get_data_to_sign_token, get_data_to_sign_certificate, sign_document_certificate, sign_document_token
from app.services.local_certs import get_certificate_from_local, get_signature_value_own
from app.utils.image_utils import  create_signature_image
from app.utils.db import get_number_and_date_then_close, unlock_pdf_and_close_task
from app.utils.saving import save_signed_pdf
from app.services.dss.dss_json import get_data_to_sign_tapir_jades, sign_document_tapir_jades
import app.exceptions.signature_exc as signatures_exc

class SignaturesService:
    def __init__(self):
        pass

    def init_signature_pdf(self, pdf, certificates):
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

        app_state.current_time = int(tiempo.time() * 1000)
        app_state.datetimesigned = datetime.now().strftime("%d/%m/%Y %H:%M:%S")

        role = name + ", " + stamp + ", " + area

        if is_digital:
            try:
                name = extract_certificate_info_name(certificates['certificate'])
            except Exception as e:
                error = ({"idDocFailed": id_doc, "message": "Error al extraer nombre del certificado: " + str(e)})
                raise Exception("Error al extraer nombre del certificado: " + str(e))
            try:
                datetime.strptime(app_state.datetimesigned, "%d/%m/%Y %H:%M:%S")
            except ValueError:
                dt = datetime.strptime(app_state.datetimesigned, "%Y-%m-%d %H:%M:%S")
                app_state.datetimesigned = dt.strftime("%d/%m/%Y %H:%M:%S")
            try:
                custom_image = create_signature_image(
                    f"{name}\n{app_state.datetimesigned}\n{stamp}\n{area}",
                    app_state.encoded_image,
                    "token"
                )
            except Exception as e:
                error = ({"idDocFailed": id_doc, "message": "Error al crear imagen de firma: " + str(e)})
                raise Exception("Error al crear imagen de firma: " + str(e))

        match (is_digital, is_closing):
            case (True, True):
                try:
                    data_to_sign_response = get_data_to_sign_token(pdf_b64, certificates, app_state.current_time, field_id, role, custom_image)
                    data_to_sign = (data_to_sign_response["bytes"])
                except Exception as e:
                    error = ({"idDocFailed": id_doc, "message": "Error al obtener datos para firmar: " + str(e)})
                    raise Exception("Error al obtener datos para firmar: " + str(e))
            case (True, False):
                try:
                    data_to_sign_response = get_data_to_sign_token(pdf_b64, certificates, app_state.current_time, field_id, role, custom_image)
                    data_to_sign = (data_to_sign_response["bytes"])
                except Exception as e:
                    error = ({"idDocFailed": id_doc, "message": "Error al obtener datos para firmar: " + str(e)})
                    raise Exception("Error al obtener datos para firmar: " + str(e))
            case (False, True):
                try:
                    signed_pdf_base64 = self.sign_own_pdf(pdf_b64, False, field_id, stamp, area, name, app_state.datetimesigned, role)
                except Exception as e:
                    error = ({"idDocFailed": id_doc, "message": "Error al firmar documento: " + str(e)})
                    raise Exception("Error al firmar documento: " + str(e))
                if not es_caratula:
                    try:
                        lastpdf = get_number_and_date_then_close(signed_pdf_base64, id_doc)
                    except Exception as e:
                        error = ({"idDocFailed": id_doc, "message": "Error al cerrar PDF: " + str(e)})
                        raise Exception("Error al cerrar PDF: " + str(e))
                else:
                    lastpdf = signed_pdf_base64
                try:
                    signed_pdf_base64_closed = self.sign_own_pdf(lastpdf, True, closing_place, stamp, area, name, app_state.datetimesigned, role)
                except Exception as e:
                    error = ({"idDocFailed": id_doc, "message": "Error al firmar documento: " + str(e)})
                    raise Exception("Error al firmar documento: " + str(e))
                finalpdf = signed_pdf_base64_closed
                is_closed = True

            case (False, False):
                try:
                    signed_pdf_base64 = self.sign_own_pdf(pdf_b64, False, field_id, stamp, area, name, app_state.datetimesigned, role)
                except Exception as e:
                    error = ({"idDocFailed": id_doc, "message": "Error al firmar documento: " + str(e)})
                    raise Exception("Error al firmar documento: " + str(e))
                finalpdf = signed_pdf_base64
                is_closed = False

        tipo_firma = 2 if is_digital else 1

        if not is_digital:
            hash_object = hashlib.sha256(io.BytesIO(base64.b64decode(finalpdf)).getvalue())
            hash_doc = hash_object.hexdigest()

            try:
                unlock_pdf_and_close_task(id_doc, id_user, hash_doc, is_closed, id_sello, id_oficina, tipo_firma)
            except Exception as e:
                error = ({"idDocFailed": id_doc, "message": "Error al desbloquear PDF: " + str(e)})
                raise Exception("Error al desbloquear PDF: " + str(e))
            try:
                save_signed_pdf(finalpdf, filepath)
            except Exception as e:
                error = ({"idDocFailed": id_doc, "message": "Error al guardar PDF firmado: " + str(e)})
                raise Exception("Error al guardar PDF firmado: " + str(e))

        return id_doc, error, data_to_sign
    
    def end_signature_pdf(self, pdfs, certificates):
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

        if is_digital:
            try:
                name = extract_certificate_info_name(certificates['certificate'])
            except Exception as e:
                error = ({"idDocFailed": id_doc, "message": "Error al extraer nombre del certificado: " + str(e)})
                raise Exception("Error al extraer nombre del certificado: " + str(e))
            try:
                datetime.strptime(app_state.datetimesigned, "%d/%m/%Y %H:%M:%S")
            except ValueError:
                dt = datetime.strptime(app_state.datetimesigned, "%Y-%m-%d %H:%M:%S")
                app_state.datetimesigned = dt.strftime("%d/%m/%Y %H:%M:%S")
            try:
                custom_image = create_signature_image(
                    f"{name}\n{app_state.datetimesigned}\n{stamp}\n{area}",
                    app_state.encoded_image,
                    "token"
                )
            except Exception as e:
                error = ({"idDocFailed": id_doc, "message": "Error al crear imagen de firma: " + str(e)})
                raise Exception("Error al crear imagen de firma: " + str(e))
        role = name + ", " + stamp + ", " + area

        match (is_digital, is_closing):
            case (True, True):
                try:
                    signed_pdf_response, code = sign_document_token(pdf_b64, signature_value, certificates, app_state.current_time, field_id, role, custom_image)
                except Exception as e:
                    error = ({"idDocFailed": id_doc, "message": "Error al firmar documento: " + str(e)})
                    raise Exception("Error al firmar documento: " + str(e))
                try:
                    lastpdf = get_number_and_date_then_close(signed_pdf_response['bytes'], id_doc)
                except Exception as e:
                    error = ({"idDocFailed": id_doc, "message": "Error al cerrar PDF: " + str(e)})
                    raise Exception("Error al cerrar PDF: " + str(e))
                try:
                    signed_pdf_base64_closed = self.sign_own_pdf(lastpdf, True, closing_place, stamp, area, name, app_state.datetimesigned, role)
                except Exception as e:
                    error = ({"idDocFailed": id_doc, "message": "Error al firmar documento: " + str(e)})
                    raise Exception("Error al firmar documento: " + str(e))
                finalpdf = signed_pdf_base64_closed
                is_closed = True

            case (True, False):
                try:
                    signed_pdf_response = sign_document_token(pdf_b64, signature_value, certificates, app_state.current_time, field_id, role, custom_image)
                except Exception as e:
                    error = ({"idDocFailed": id_doc, "message": "Error al firmar documento: " + str(e)})
                    raise Exception("Error al firmar documento: " + str(e))
                finalpdf = signed_pdf_response['bytes']
                is_closed = False
        
        hash_object = hashlib.sha256(io.BytesIO(base64.b64decode(finalpdf)).getvalue())
        hash_doc = hash_object.hexdigest()

        tipo_firma = 2 if is_digital else 1

        try:
            unlock_pdf_and_close_task(id_doc, id_user, hash_doc, is_closed, id_sello, id_oficina, tipo_firma)
        except Exception as e:
            error = ({"idDocFailed": id_doc, "message": "Error al desbloquear PDF: " + str(e)})
            raise Exception("Error al desbloquear PDF: " + str(e))
        try:
            save_signed_pdf(finalpdf, filepath)
        except Exception as e:
            error = ({"idDocFailed": id_doc, "message": "Error al guardar PDF firmado: " + str(e)})
            raise Exception("Error al guardar PDF firmado: " + str(e))
        
        return id_doc, error
    
    def init_sign_jades(self, index_data, certificates, data_signature):
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
                    name = extract_certificate_info_name(certificates['certificate'])
                except Exception as e:
                    error = ({"idExpFailed": f"{index['numero']}/{index['anio']}/{index['codigo']}/{index['letra']}", "message": "Error al extraer nombre del certificado: " + str(e)})
                    raise Exception("Error al extraer nombre del certificado: " + str(e))
            role = name + ", " + stamp + ", " + area

            if isdigital:
                try:
                    data_to_sign_response = get_data_to_sign_tapir_jades(jsonb64, certificates, app_state.current_time, role)
                    data_to_sign = data_to_sign_response["bytes"]
                except Exception as e:
                    error = ({"idExpFailed": f"{index['numero']}/{index['anio']}/{index['codigo']}/{index['letra']}", "message": "Error al obtener datos para firmar: " + str(e)})
                    raise Exception("Error al obtener datos para firmar: " + str(e))
            else:
                try:
                    signed_json_b64 = self.sign_own_jades(jsonb64, role)
                except Exception as e:
                    error = ({"idExpFailed": f"{index['numero']}/{index['anio']}/{index['codigo']}/{index['letra']}", "message": "Error al firmar documento: " + str(e)})
                    raise Exception("Error al firmar documento: " + str(e))
                tramite['firma'] = signed_json_b64

            if not isdigital:
                id_exp_signed = (f"{index['numero']}/{index['anio']}/{index['codigo']}/{index['letra']}")
                index_signed = index

        except Exception as e:
            pass
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
                    name = extract_certificate_info_name(certificates['certificate'])
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

    def sign_own_pdf(self, pdf, is_yunga_sign, field_to_sign, stamp, area, name, datetime_signed, role):
        """
        Firma el PDF con certificado propio del servidor.

        Args:
            pdf (str): Base64 encoded PDF to sign.
            is_yunga_sign (bool): Flag indicating if it's a Yunga sign.
            field_to_sign (str): Field to sign.
            stamp (str): Stamp information.
            area (str): Area information.
            name (str): Name of the signer.
            datetime_signed (str): Datetime of the signature.

        Returns:
            str: Base64 encoded signed PDF.
            int: HTTP status code.
        """
        try:
            # Convert from Y-m-d to d/m/Y format
            try:
                datetime.strptime(datetime_signed, "%d/%m/%Y %H:%M:%S")
            except ValueError:
                dt = datetime.strptime(datetime_signed, "%Y-%m-%d %H:%M:%S") 
                app_state.datetime_signed = dt.strftime("%d/%m/%Y %H:%M:%S")
            if not is_yunga_sign:
                try:
                    custom_image = create_signature_image(f"{name}\n{datetime_signed}\n{stamp}\n{area}", app_state.encoded_image, "cert")
                except Exception as e:
                    raise Exception("Error al crear imagen de firma: " + str(e))
            else:
                try:
                    custom_image = create_signature_image(f"Sistema Yunga TC Tucumán\n{app_state.datetime_signed}", app_state.encoded_image, "yunga")
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
        
    def create_and_sign(pdf, certificates, field_to_sign, role, custom_image):
        try:
            data_to_sign_response = get_data_to_sign_certificate(pdf, certificates, app_state.current_time, field_to_sign, role, custom_image)
        except Exception as e:
            raise Exception("Error al obtener datos para firmar: " + str(e))
        try:
            data_to_sign = data_to_sign_response["bytes"]
            signature_value = get_signature_value_own(data_to_sign)
        except Exception as e:
            raise Exception("Error al obtener valor de firma: " + str(e))
        try:
            signed_pdf_response = sign_document_certificate(pdf, signature_value, certificates, app_state.current_time, field_to_sign, role, custom_image)
        except Exception as e:
            raise Exception("Error al firmar documento: " + str(e))
        return signed_pdf_response['bytes']
    
    def sign_own_jades(json, role):
        """
        Sign a JADES document using the own signature method.
        """
        try:
            certificates = get_certificate_from_local()
        except Exception as e:
            raise Exception("Error al obtener certificado local: " + str(e))
        try:
            data_to_sign_response = get_data_to_sign_tapir_jades(json, certificates, app_state.current_time, role)
        except Exception as e:
            raise Exception("Error al obtener datos para firmar: " + str(e))
        data_to_sign_bytes = data_to_sign_response["bytes"]
        try:
            signature_value = get_signature_value_own(data_to_sign_bytes)
        except Exception as e:
            raise Exception("Error al obtener valor de firma: " + str(e))
        try:
            signed_json_response = sign_document_tapir_jades(json, signature_value, certificates, app_state.current_time, role)
        except Exception as e:
            raise Exception("Error al firmar documento: " + str(e))
        return signed_json_response['bytes']
