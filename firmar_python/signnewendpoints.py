from flask import Flask, request, jsonify, send_from_directory, Blueprint
import base64
import time as tiempo
import logging
from dss_sign import *
from dss_sign_own import *
from dss_sign_tapir import *
from manage_pdf import *
from localcerts import *
from certificates import *
from nexu import *
from errors import PDFSignatureError
import json
from imagecomp import *
from datetime import *
import pytz
from pdfrw import *
from signimagepregenerated import *

firma_bp = Blueprint('firma', __name__)

###    Variables globales     ###
datetimesigned = None
pdf_b64 = None
current_time = None
certificates = None
signed_pdf_filename = None
field_id = None
stamp = None
area = None
name = None
custom_image = None
isdigital = None
isclosing = None
closingplace = None
closing_number = None
closing_date = None
fieldValues = None
signed_pdf_filename = None
##################################################

###    Funcion de guardado de PDF     ###
def save_signed_pdf(signed_pdf_base64, filename):
    try:
        signed_pdf_bytes = base64.b64decode(signed_pdf_base64)
        with open(filename, 'wb') as f:
            f.write(signed_pdf_bytes)
    except Exception as e:
        logging.error(f"Error in save_signed_pdf: {str(e)}")
        raise PDFSignatureError("Failed to save signed PDF.")
###################################################


### Imagen de firma en base64 ###
encoded_image = encode_image("logo_tribunal_para_tapir.png")
compressedimage = compressed_image_encoded("logo_tribunal_para_tapir.png")


###    Rutas de la aplicacion para Tapir     ###

@firma_bp.route('/firma_init', methods=['POST'])
def get_certificates():
    global pdf_b64, current_time, certificates, signed_pdf_filename, field_id, stamp, area, name, datetimesigned, custom_image, isdigital, isclosing, closingplace, closing_number, closing_date, fieldValues, signed_pdf_filename
    
    try:   
        request._load_form_data()
        pdf_b64 = request.form.get('pdf')
        
        # Verificar que el campo 'certificados' esté presente y no esté vacío
        certificados_str = request.form.get('certificados', '')
        if not certificados_str:
            raise PDFSignatureError("El campo 'certificados' está vacío o falta.")

        # Intentar analizar el campo 'certificados' como JSON
        try:
            certificates = json.loads(certificados_str)
        except json.JSONDecodeError:
            raise PDFSignatureError("Formato JSON inválido para 'certificados'.")

        # Repetir un proceso similar para 'firma_info'
        firma_info_str = request.form.get('firma_info', '')
        if not firma_info_str:
            raise PDFSignatureError("El campo 'firma_info' está vacío o falta.")

        try:
            sign_info = json.loads(firma_info_str)
        except json.JSONDecodeError:
            raise PDFSignatureError("Formato JSON inválido para 'firma_info'.")

        try:
            signed_pdf_filename = request.form.get('file_name')
        except KeyError:
            raise PDFSignatureError("file_name is missing")
        
        field_id = sign_info.get('firma_lugar')
        name = sign_info.get('firma_nombre')
        stamp = sign_info.get('firma_sello')
        area = sign_info.get('firma_area')
        isdigital = sign_info.get('firma_digital')
        isclosing = sign_info.get('firma_cierra')
        closingplace = sign_info.get('firma_lugarcierre')
        closing_number = sign_info.get('numero_doc')
        closing_date = sign_info.get('fecha_doc')
        fieldValues = {
            "numero": closing_number,
            "fecha": closing_date
        }

        current_time = int(tiempo.time() * 1000)
        datetimesigned = datetime.now(pytz.utc).astimezone(pytz.timezone('America/Argentina/Buenos_Aires')).strftime("%Y-%m-%d %H:%M:%S")

        if not field_id or not stamp or not area:
            raise PDFSignatureError("firma_info is missing required fields")

        if not name:
            name = extract_certificate_info_name(certificates['certificate'])

        custom_image = create_signature_image(
                        f"{name}\n{datetimesigned}\n{stamp}\n{area}",
                        encoded_image
                    )   

        match (isdigital, isclosing):
            case (True, True):
                data_to_sign_response = get_data_to_sign_tapir(pdf_b64, certificates, current_time, field_id, stamp, custom_image)
                data_to_sign = data_to_sign_response["bytes"]
            case (True, False):
                data_to_sign_response = get_data_to_sign_tapir(pdf_b64, certificates, current_time, field_id, stamp, custom_image)
                data_to_sign = data_to_sign_response["bytes"]
            case (False, True):
                signed_pdf_base64 = signown(pdf_b64, False)
                signed_pdf_base64 = signown(signed_pdf_base64, True)
                lastpdf = closePDF(signed_pdf_base64)
                save_signed_pdf(lastpdf, signed_pdf_filename+"signEandclose.pdf")
            case (False, False):
                lastpdf = signown(pdf_b64, False)
                save_signed_pdf(lastpdf, signed_pdf_filename+"signE.pdf")
        
        if isdigital:
            return jsonify({"status": "success", "data_to_sign": data_to_sign}), 200
        else:
            return jsonify({"status": "success", "pdf": lastpdf}), 200
        
    except PDFSignatureError as e:
        return jsonify({"status": "error", "message": str(e)}), 500
    except Exception as e:
        logging.error(f"Unexpected error in get_certificates: {str(e)}")
        return jsonify({"status": "error", "message": "An unexpected error occurred."}), 500

@firma_bp.route('/firma_valor', methods=['POST'])
def sign_pdf_firmas():
    try:

        signature_value = request.get_json()['signatureValue']
        signed_pdf_response = sign_document_tapir(pdf_b64, signature_value, certificates, current_time, field_id, stamp, custom_image)
        signed_pdf_base64 = signed_pdf_response['bytes']

        match (isdigital, isclosing):
            case (True, True):
                lastsignedpdf = signown(signed_pdf_base64, True)
                lastpdf = closePDF(lastsignedpdf)
                save_signed_pdf(lastpdf, signed_pdf_filename+"signDandclose.pdf")
                return jsonify({"status": "success", "pdf": lastpdf}), 200
            case (True, False):
                save_signed_pdf(signed_pdf_base64, signed_pdf_filename+"signD.pdf")
                return jsonify({"status": "success", "pdf": signed_pdf_base64}), 200

    except Exception as e:
        logging.error(f"Unexpected error in sign_pdf_firmas: {str(e)}")
        return jsonify({"status": "error", "message": "An unexpected error occurred."}), 500

def signown(pdf, isSigned):
    try:
        if not isSigned and isclosing or not isSigned and not isclosing:
            data_to_sign_response = get_data_to_sign_own(pdf, certificates, current_time, field_id, stamp, custom_image)
            data_to_sign = data_to_sign_response["bytes"]
            signature_value = get_signature_value_own(data_to_sign)
            signed_pdf_response = sign_document_own(pdf, signature_value, certificates, current_time, field_id, stamp, custom_image)
            signed_pdf_base64 = signed_pdf_response['bytes']
            return signed_pdf_base64
        else:
            custom_image = create_signature_image(
                f"Sistema Yunga TC Tucumán\n{datetimesigned}",
                encoded_image
            )
            data_to_sign_response = get_data_to_sign_own(pdf, certificates, current_time, closingplace, stamp, custom_image)
            data_to_sign = data_to_sign_response["bytes"]
            signature_value = get_signature_value_own(data_to_sign)
            signed_pdf_response = sign_document_own(pdf, signature_value, certificates, current_time, closingplace, stamp, custom_image)
            signed_pdf_base64 = signed_pdf_response['bytes']
            return signed_pdf_base64
    except PDFSignatureError as e:
        return jsonify({"status": "error", "message": str(e)}), 500

def closePDF(pdftoclose):
    try:
        data = {
                    'fileBase64': pdftoclose,
                    'fileName': signed_pdf_filename,
                    'fieldValues': fieldValues
                }
        response = requests.post('http://java-webapp:5555/pdf/update', data=data)
        response.raise_for_status()
        signed_pdf_base64 = base64.b64encode(response.content).decode('utf-8')
        return signed_pdf_base64

    except PDFSignatureError as e:
        return jsonify({"status": "error", "message": str(e)}), 500
    except Exception as e:
        logging.error(f"Unexpected error in sign_own_pdf: {str(e)}")
        return jsonify({"status": "error", "message": "An unexpected error occurred."}), 500
