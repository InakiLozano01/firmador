##################################################
###              Imports externos              ###
##################################################

from flask import Flask, request, jsonify
import base64
import time as tiempo
import logging
import os
import json
from datetime import *
import pytz
import psycopg2
import hashlib

##################################################
###              Imports propios               ###
##################################################

from dss_sign import *
from localcerts import *
from certificates import *
from errors import PDFSignatureError
from imagecomp import *
from createimagetostamp import *

load_dotenv()

##################################################
###      Configuracion de aplicacion Flask     ###
##################################################

app = Flask(__name__)

logging.basicConfig(level=logging.DEBUG, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

if __name__ == '__main__':
    app.run(host='0.0.0.0', debug=True, port=5000)

##################################################
###            Variables globales              ###
##################################################

datetimesigned = None
pdf = None
current_time = None
certificates = None
signed_pdf_filename = None
field_id = None
stamp = None
area = None
name = None
custom_image = None
pdf_b64 = None
isdigital = None
isclosing = None
closingplace = None
json_fieldValues = None
idDoc = None
conn = None

##################################################
###         Imagen de firma en base64          ###
##################################################

encoded_image = encode_image("logo_tribunal_para_tapir_250px.png")
#compressedimage = compressed_image_encoded("logo_tribunal_para_tapir.png")

##################################################
###         Funcion de guardado de PDF         ###
##################################################

def save_signed_pdf(signed_pdf_base64, filename):
    try:
        signed_pdf_bytes = base64.b64decode(signed_pdf_base64)
        with open(filename, 'wb') as f:
            f.write(signed_pdf_bytes)
        return jsonify({"status": True, "message": "PDF firmado guardado correctamente."}), 200
    except Exception as e:
        logging.error(f"Error in save_signed_pdf: {str(e)}")
        return jsonify({"status": False, "message": "Error al guardar el PDF firmado."}), 500

##################################################
###     Rutas de la aplicacion para Tapir      ###
##################################################

@app.route('/firma_init', methods=['POST'])
def get_certificates():
    global pdf_b64, current_time, certificates, field_id, stamp, area, name, datetimesigned, custom_image, isdigital, isclosing, closingplace, signed_pdf_filename, idDoc
    
    try:   
        request._load_form_data()
        pdf_b64 = request.form.get('pdf')
        now = datetime.now()
        signed_pdf_filename = now.strftime("pdf_%d/%m/%Y_%H%M%S")

        firma_info_str = request.form.get('firma_info', '')
        if not firma_info_str:
            raise PDFSignatureError("El campo 'firma_info' está vacío o falta.")

        try:
            sign_info = json.loads(firma_info_str)
        except json.JSONDecodeError:
            raise PDFSignatureError("Formato JSON inválido para 'firma_info'.")
        
        isdigital = sign_info.get('firma_digital')

        # Solo intentar cargar y verificar 'certificados' si 'isdigital' es verdadero
        if isdigital:
        # Verificar que el campo 'certificados' esté presente y no esté vacío
            certificados_str = request.form.get('certificados', '')
            if not certificados_str and isdigital:
                raise PDFSignatureError("El campo 'certificados' está vacío o falta.")

            # Intentar analizar el campo 'certificados' como JSON
            try:
                certificates = json.loads(certificados_str)
            except json.JSONDecodeError:
                raise PDFSignatureError("Formato JSON inválido para 'certificados'.")
        
        try:
            signed_pdf_filename = request.form.get('file_name')
        except KeyError:
            raise PDFSignatureError("El campo file_name is missing")
        
        field_id = sign_info.get('firma_lugar')
        name = sign_info.get('firma_nombre')
        stamp = sign_info.get('firma_sello')
        area = sign_info.get('firma_area')
        
        isclosing = sign_info.get('firma_cierra')
        closingplace = sign_info.get('firma_lugarcierre')
        idDoc = sign_info.get('id_doc')

        current_time = int(tiempo.time() * 1000)
        datetimesigned = datetime.now(pytz.utc).astimezone(pytz.timezone('America/Argentina/Buenos_Aires')).strftime("%Y-%m-%d %H:%M:%S")

        if not field_id or not stamp or not area:
            raise PDFSignatureError("firma_info is missing required fields")

        if isdigital:
            name = extract_certificate_info_name(certificates['certificate'])

        custom_image = create_signature_image(
                        f"{name}\n{datetimesigned}\n{stamp}\n{area}",
                        encoded_image,
                        "token"
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
                lastpdf, code = get_number_and_date_then_close(signed_pdf_base64, idDoc)
                if code == 500:
                    response = lastpdf.get_json()
                    if response['status'] == "error":
                        return jsonify({"status": "error", "message": "Error al cerrar PDF: " + response['message']}), 500
                signed_pdf_base64_closed = signown(lastpdf, True)
                save_signed_pdf(signed_pdf_base64_closed, signed_pdf_filename+"signEandclose.pdf")
            case (False, False):
                signed_pdf_base64_closed = signown(pdf_b64, False)
                save_signed_pdf(signed_pdf_base64_closed, signed_pdf_filename+"signE.pdf")
        
        if isdigital:
            return jsonify({"status": True, "data_to_sign": data_to_sign}), 200
        else:
            return jsonify({"status": True, "pdf": signed_pdf_base64_closed}), 200
        
    except PDFSignatureError as e:
        return jsonify({"status": "error", "message": "Error en get_certificates: " + str(e)}), 500
    except Exception as e:
        logging.error(f"Unexpected error in get_certificates: {str(e)}")
        return jsonify({"status": "error", "message": "An unexpected error occurred in get_certificates."}), 500

@app.route('/firma_valor', methods=['POST'])
def sign_pdf_firmas():
    try:

        signature_value = request.get_json()['signatureValue']
        signed_pdf_response = sign_document_tapir(pdf_b64, signature_value, certificates, current_time, field_id, stamp, custom_image)
        signed_pdf_base64 = signed_pdf_response['bytes']

        match (isdigital, isclosing):
            case (True, True):
                lastpdf, code = get_number_and_date_then_close(signed_pdf_base64, idDoc)
                if code == 500:
                    response = lastpdf.get_json()
                    if response['status'] == "error":
                        return jsonify({"status": "error", "message": "Error al cerrar PDF: " + response['message']}), 500
                lastsignedpdf = signown(lastpdf, True)
                save_signed_pdf(lastsignedpdf, signed_pdf_filename+"signDandclose.pdf")
                return jsonify({"status": True, "pdf": lastsignedpdf}), 200
            case (True, False):
                save_signed_pdf(signed_pdf_base64, signed_pdf_filename+"signD.pdf")
                return jsonify({"status": True, "pdf": signed_pdf_base64}), 200

    except Exception as e:
        logging.error(f"Unexpected error in sign_pdf_firmas: {str(e)}")
        return jsonify({"status": "error", "message": "An unexpected error occurred in sign_pdf_firmas."}), 500

##################################################
###       Función para firmar el PDF con       ###
###       certificado propio del servidor      ###
##################################################

def signown(pdf, isYungaSign, fieldtosign, stamp, area, name, datetimesigned):
    try:
        if not isYungaSign and isclosing or not isYungaSign and not isclosing:
            custom_image, code = create_signature_image(
                f"{name}\n{datetimesigned}\n{stamp}\n{area}",
                encoded_image,
                "cert"
            )
            if code != 200:
                return jsonify({"status": False, "message": "Error al crear imagen de firma"}), 500
            certificates, code = get_certificate_from_local()
            if code != 200:
                return jsonify({"status": False, "message": "Error al obtener certificado local"}), 500
            data_to_sign_response, code = get_data_to_sign_own(pdf, certificates, current_time, fieldtosign, stamp, custom_image)
            if code != 200:
                return jsonify({"status": False, "message": "Error al obtener datos para firmar"}), 500
            data_to_sign = data_to_sign_response["bytes"]
            signature_value, code = get_signature_value_own(data_to_sign)
            if code != 200:
                return jsonify({"status": False, "message": "Error al obtener valor de firma"}), 500
            signed_pdf_response, code = sign_document_own(pdf, signature_value, certificates, current_time, fieldtosign, stamp, custom_image)
            if code != 200:
                return jsonify({"status": False, "message": "Error al firmar documento"}), 500
            signed_pdf_base64 = signed_pdf_response['bytes']
            return signed_pdf_base64, 200
        else:
            custom_image, code = create_signature_image(
                f"Sistema Yunga TC Tucumán\n{datetimesigned}",
                encoded_image,
                "yunga"
            )
            if code != 200:
                return jsonify({"status": False, "message": "Error al crear imagen de firma"}), 500
            certificates, code = get_certificate_from_local()
            if code != 200:
                return jsonify({"status": False, "message": "Error al obtener certificado local"}), 500
            data_to_sign_response, code = get_data_to_sign_own(pdf, certificates, current_time, fieldtosign, stamp, custom_image)
            if code != 200:
                return jsonify({"status": False, "message": "Error al obtener datos para firmar"}), 500
            data_to_sign = data_to_sign_response["bytes"]
            signature_value, code = get_signature_value_own(data_to_sign)
            if code != 200:
                return jsonify({"status": False, "message": "Error al obtener valor de firma"}), 500
            signed_pdf_response, code = sign_document_own(pdf, signature_value, certificates, current_time, fieldtosign, stamp, custom_image)
            if code != 200:
                return jsonify({"status": False, "message": "Error al firmar documento"}), 500
            signed_pdf_base64 = signed_pdf_response['bytes']
            return signed_pdf_base64, 200
    except PDFSignatureError as e:
        print("Exception en signown")
        return jsonify({"status": "error", "message": "Error en signown: " + str(e)}), 500