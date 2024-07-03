###################################################
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
from dotenv import load_dotenv
import psycopg2
###################################################

firma_bp = Blueprint('firma', __name__)

load_dotenv()
##################################################
###    Variables globales     ###
##################################################
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
json_fieldValues = None
##################################################

###    Funcion de guardado de PDF     ###
###################################################
def save_signed_pdf(signed_pdf_base64, filename):
    try:
        print("Guardando PDF")
        signed_pdf_bytes = base64.b64decode(signed_pdf_base64)
        with open(filename, 'wb') as f:
            print("Guardando PDF with")
            f.write(signed_pdf_bytes)
    except Exception as e:
        logging.error(f"Error in save_signed_pdf: {str(e)}")
        raise PDFSignatureError("Failed to save signed PDF.")
###################################################


### Imagen de firma en base64 ###
###################################################
encoded_image = encode_image("logo_tribunal_para_tapir.png")
compressedimage = compressed_image_encoded("logo_tribunal_para_tapir.png")
###################################################

###    Rutas de la aplicacion para Tapir     ###
###################################################
@firma_bp.route('/firma_init', methods=['POST'])
def get_certificates():
    global pdf_b64, current_time, certificates, signed_pdf_filename, field_id, stamp, area, name, datetimesigned, custom_image, isdigital, isclosing, closingplace, closing_number, closing_date, fieldValues, signed_pdf_filename, json_fieldValues
    
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
            raise PDFSignatureError("file_name is missing")
        
        field_id = sign_info.get('firma_lugar')
        name = sign_info.get('firma_nombre')
        stamp = sign_info.get('firma_sello')
        area = sign_info.get('firma_area')
        
        isclosing = sign_info.get('firma_cierra')
        closingplace = sign_info.get('firma_lugarcierre')
        idDoc = sign_info.get('id_doc')
        closing_number, closing_date  = get_closing_number_and_date(idDoc)
        fieldValues = {
            "numero": closing_number,
            "fecha": closing_date
        }
        json_fieldValues = json.dumps(fieldValues)

        current_time = int(tiempo.time() * 1000)
        datetimesigned = datetime.now(pytz.utc).astimezone(pytz.timezone('America/Argentina/Buenos_Aires')).strftime("%Y-%m-%d %H:%M:%S")

        if not field_id or not stamp or not area:
            raise PDFSignatureError("firma_info is missing required fields")

        if isdigital:
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
                lastpdf = closePDF(signed_pdf_base64)
                signed_pdf_base64_closed = signown(lastpdf, True)
                save_signed_pdf(signed_pdf_base64_closed, signed_pdf_filename+"signEandclose.pdf")
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
###################################################

###################################################
@firma_bp.route('/firma_valor', methods=['POST'])
def sign_pdf_firmas():
    try:

        signature_value = request.get_json()['signatureValue']
        signed_pdf_response = sign_document_tapir(pdf_b64, signature_value, certificates, current_time, field_id, stamp, custom_image)
        signed_pdf_base64 = signed_pdf_response['bytes']

        match (isdigital, isclosing):
            case (True, True):
                lastpdf = closePDF(signed_pdf_base64)
                lastsignedpdf = signown(lastpdf, True)
                save_signed_pdf(lastsignedpdf, signed_pdf_filename+"signDandclose.pdf")
                return jsonify({"status": "success", "pdf": lastpdf}), 200
            case (True, False):
                save_signed_pdf(signed_pdf_base64, signed_pdf_filename+"signD.pdf")
                return jsonify({"status": "success", "pdf": signed_pdf_base64}), 200

    except Exception as e:
        logging.error(f"Unexpected error in sign_pdf_firmas: {str(e)}")
        return jsonify({"status": "error", "message": "An unexpected error occurred."}), 500
###################################################


### Funciones ###
# Función para firmar el PDF con certificado propio del servidor #
###################################################
def signown(pdf, isSignedYet):
    try:
        if not isSignedYet and isclosing or not isSignedYet and not isclosing:
            custom_image = create_signature_image(
                f"{name}\n{datetimesigned}\n{stamp}\n{area}",
                encoded_image
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
                encoded_image
            )
            certificates = get_certificate_from_local()
            data_to_sign_response = get_data_to_sign_own(pdf, certificates, current_time, closingplace, stamp, custom_image)
            data_to_sign = data_to_sign_response["bytes"]
            signature_value = get_signature_value_own(data_to_sign)
            signed_pdf_response = sign_document_own(pdf, signature_value, certificates, current_time, closingplace, stamp, custom_image)
            signed_pdf_base64 = signed_pdf_response['bytes']
            return signed_pdf_base64
    except PDFSignatureError as e:
        return jsonify({"status": "error", "message": str(e)}), 500
###################################################
# Función para cerrar el PDF #
###################################################
def closePDF(pdftoclose):
    try:
        data = {
                    'fileBase64': pdftoclose,
                    'fileName': signed_pdf_filename,
                    'fieldValues': json_fieldValues
                }
        response = requests.post('http://java-webapp:5555/pdf/update', data=data)
        response.raise_for_status()
        signed_pdf_base64 = base64.b64encode(response.content).decode("utf-8")
        return signed_pdf_base64

    except PDFSignatureError as e:
        return jsonify({"status": "error", "message": str(e)}), 500
    except Exception as e:
        logging.error(f"Unexpected error in sign_own_pdf: {str(e)}")
        return jsonify({"status": "error", "message": "An unexpected error occurred."}), 500
###################################################
# Función para obtener el número de cierre y la fecha de cierre #    
###################################################
def get_closing_number_and_date(idDoc):
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
        conn.autocommit = False  # Desactivar el autocommit para manejar transacciones manualmente
        cursor = conn.cursor()
        try:
            funcion_sql = "SELECT f_documento_protocolizar(%s);"
            idDoc = 6
            cursor.execute(funcion_sql, idDoc)

            datos = cursor.fetchone()
            print(datos)
        except Exception as e:
            print("Error en la transacción", e)
            return jsonify({"status": "error", "message": "Error en la transacción"}), 500
        finally:
            cursor.close()
    except Exception as e:
        print("Error al conectar a la base de datos:", e)
        return jsonify({"status": "error", "message": "Error al conectar a la base de datos"}), 500
    finally:
        if conn:
            conn.close()
###################################################
