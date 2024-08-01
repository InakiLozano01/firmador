##################################################
###              Imports externos              ###
##################################################

from flask import Flask, request, jsonify, send_from_directory
import base64
import time as tiempo
import logging
import os
import json
from datetime import *
import pytz
import psycopg2

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
closing_number = None
closing_date = None
fieldValues = None
json_fieldValues = None
idDoc = None

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
    except Exception as e:
        logging.error(f"Error in save_signed_pdf: {str(e)}")
        raise PDFSignatureError("Failed to save signed PDF.")

##################################################
###     Rutas de la aplicacion para Tapir      ###
##################################################

@app.route('/firma_init', methods=['POST'])
def get_certificates():
    global pdf_b64, current_time, certificates, signed_pdf_filename, field_id, stamp, area, name, datetimesigned, custom_image, isdigital, isclosing, closingplace, closing_number, closing_date, fieldValues, signed_pdf_filename, json_fieldValues, idDoc
    
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
            return jsonify({"status": "success", "data_to_sign": data_to_sign}), 200
        else:
            return jsonify({"status": "success", "pdf": signed_pdf_base64_closed}), 200
        
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
                return jsonify({"status": "success", "pdf": lastsignedpdf}), 200
            case (True, False):
                save_signed_pdf(signed_pdf_base64, signed_pdf_filename+"signD.pdf")
                return jsonify({"status": "success", "pdf": signed_pdf_base64}), 200

    except Exception as e:
        logging.error(f"Unexpected error in sign_pdf_firmas: {str(e)}")
        return jsonify({"status": "error", "message": "An unexpected error occurred in sign_pdf_firmas."}), 500

##################################################
###       Función para firmar el PDF con       ###
###       certificado propio del servidor      ###
##################################################

def signown(pdf, isYungaSign):
    try:
        if not isYungaSign and isclosing or not isYungaSign and not isclosing:
            custom_image = create_signature_image(
                f"{name}\n{datetimesigned}\n{stamp}\n{area}",
                encoded_image,
                "cert"
            )
            certificates = get_certificate_from_local()
            data_to_sign_response = get_data_to_sign_own(pdf, certificates, current_time, field_id, stamp, custom_image)
            data_to_sign = data_to_sign_response["bytes"]
            signature_value = get_signature_value_own(data_to_sign)
            signed_pdf_response = sign_document_own(pdf, signature_value, certificates, current_time, field_id, stamp, custom_image)
            signed_pdf_base64 = signed_pdf_response['bytes']
            return signed_pdf_base64
        else:
            custom_image = create_signature_image(
                f"Sistema Yunga TC Tucumán\n{datetimesigned}",
                encoded_image,
                "yunga"
            )
            certificates = get_certificate_from_local()
            data_to_sign_response = get_data_to_sign_own(pdf, certificates, current_time, closingplace, stamp, custom_image)
            data_to_sign = data_to_sign_response["bytes"]
            signature_value = get_signature_value_own(data_to_sign)
            signed_pdf_response = sign_document_own(pdf, signature_value, certificates, current_time, closingplace, stamp, custom_image)
            signed_pdf_base64 = signed_pdf_response['bytes']
            return signed_pdf_base64
    except PDFSignatureError as e:
        return jsonify({"status": "error", "message": "Error en signown: " + str(e)}), 500

##################################################
###         Función para cerrar el PDF         ###
##################################################

def closePDF(pdfToClose):
    try:
        data = {
                    'fileBase64': pdfToClose,
                    'fileName': signed_pdf_filename,
                    'fieldValues': json_fieldValues
                }
        response = requests.post('http://java-webapp:5555/pdf/update', data=data)
        response.raise_for_status()
        signed_pdf_base64 = base64.b64encode(response.content).decode("utf-8")
        return signed_pdf_base64, 200
    except PDFSignatureError as e:
        return jsonify({"status": "error", "message": "Error cerrando el PDF: " + str(e)}), 500
    except Exception as e:
        logging.error(f"Unexpected error in closePDF: {str(e)}")
        return jsonify({"status": "error", "message": "An unexpected error occurred in closePDF"}), 500

###################################################
###      Función para obtener el número de      ###
###         cierre y la fecha de cierre         ###
###################################################

def get_number_and_date_then_close(pdfToClose, idDoc):
    global json_fieldValues
    dbname = os.getenv('DB_NAME')
    user = os.getenv('DB_USER')
    password = os.getenv('DB_PASSWORD')
    host = os.getenv('DB_HOST')
    port = os.getenv('DB_PORT')

    # Detalles de conexión
    conn_params = {
        'dbname': dbname,
        'user': user,
        'password': password,
        'host': host,
        'port': port  # Puerto por defecto de PostgreSQL
    }
    try:
        # Establecer la conexión
        conn = psycopg2.connect(**conn_params)
        cursor = conn.cursor()
        try:
            cursor.execute("SELECT f_documento_protocolizar(%s)", (idDoc,))

            datos = cursor.fetchone()
            datos_json = json.loads(json.dumps(datos[0]))
            print(datos)
            print(datos_json)
            print(type(datos_json))
            json_fieldValues1 = {
                "numero": datos_json['numero'],
                "fecha": datos_json['fecha']
            }
            json_fieldValues = json.dumps(json_fieldValues1)
            
            if datos_json['status'] == False:
                raise Exception("Error al obtener fecha y numero: " + datos_json['message'])
            else:
                try:
                    pdf, code = closePDF(pdfToClose)
                    if code == 500:
                        response = pdf.get_json()
                        if response['status'] == "error":
                            conn.rollback()
                            return jsonify({"status": "error", "message": "Error al cerrar PDF: " + response['message']}), 500
                except Exception as e:
                    conn.rollback()
                    return jsonify({"status": "error", "message": "Error al cerrar PDF: " + str(e)}), 500
                conn.commit()
                return pdf, 200
        except Exception as e:
            conn.rollback()
            return jsonify({"status": "error", "message": "Error transaccion: " + str(e)}), 500
        finally:
            cursor.close()
    except Exception as e:
        return jsonify({"status": "error", "message": "Error al conectar a la base de datos: " + str(e)}), 500
    finally:
        if conn:
            conn.close()

@app.route('/firmalote', methods=['POST'])
def firmalote():
    return "En desarrollo"