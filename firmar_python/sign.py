##################################################
###              Imports externos              ###
##################################################
import base64
import io
import time as tiempo
import logging
import os
import json
import copy
from datetime import datetime
import hashlib
import unicodedata
import libarchive
import pytz
import psycopg2
from dotenv import load_dotenv
import requests
from flask import Flask, request, jsonify
from time import time

##################################################
###              Imports propios               ###
##################################################
from dss_sign import get_data_to_sign_own, sign_document_own, get_data_to_sign_tapir, sign_document_tapir, get_data_to_sign_tapir_jades, sign_document_tapir_jades
from localcerts import get_certificate_from_local, get_signature_value_own
from certificates import extract_certificate_info_name
from errors import PDFSignatureError
from imagecomp import encode_image
from createimagetostamp import create_signature_image
from validation import validate_certs, validate_signature, validation_analyze
from watermark import merge_pdf_files_pdfrw, add_watermark_to_pdf

##################################################
###         Cargar variables de entorno        ###
##################################################
load_dotenv()

##################################################
###      Configuracion de aplicacion Flask     ###
##################################################
app = Flask(__name__)
app.config['MAX_CONTENT_LENGTH'] = 500000000
app.json.sort_keys = False


logging.basicConfig(level=logging.DEBUG, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

if __name__ == '__main__':
    app.run(host='0.0.0.0', debug=True, port=5000)

##################################################
###            Variables globales              ###
##################################################
datetimesigned = None
current_time = None
conn = None
isclosing = None

##################################################
###         Imagen de firma en base64          ###
##################################################
encoded_image = encode_image("logo_tribunal_para_tapir_250px.png")

##################################################
###         Funcion de guardado de PDF         ###
##################################################
def save_signed_pdf(signed_pdf_base64, filename):
    """
    Guarda el PDF firmado en un archivo.

    Argumetos:
        signed_pdf_base64 (str): PDF firmado en Base64.
        filename (str): Nombre del archivo a guardar en PDF.

    Returns:
        Response: JSON.
    """
    try:
        signed_pdf_bytes = base64.b64decode(signed_pdf_base64)
        with open(filename, 'wb') as f:
            dirpath = os.path.dirname(filename)
            if not os.path.exists(dirpath):
                os.makedirs(dirpath)
            f.write(signed_pdf_bytes)
        return jsonify({"status": True, "message": "PDF firmado guardado correctamente."}), 200
    except Exception as e:
        logging.error("Error in save_signed_pdf: %s", str(e))
        return jsonify({"status": False, "message": "Error al guardar el PDF firmado."}), 500

##################################################
###        Función para guardar el JSON        ###
##################################################
def save_signed_json(index, filepath):
    try:
        with open(filepath, 'w') as file:
            json.dump(index, file, separators=(',', ':'), ensure_ascii=False)
        return True, 200
    except Exception as e:
        return jsonify({"status": False, "message": "Error al guardar el indice firmado: " + str(e)}), 500

##################################################
###       Función para firmar el JSON con      ###
###       certificado propio del servidor      ###
##################################################
def sign_own_jades(json, role):
    """
    Sign a JADES document using the own signature method.
    """
    global current_time
    try:
        certificates, code = get_certificate_from_local()
        if code != 200:
            return jsonify({"status": False, "message": "Error al obtener certificado local"}), 500
        data_to_sign_response, code = get_data_to_sign_tapir_jades(json, certificates, current_time, role)
        if code == 500:
            return jsonify({"status": False, "message": "Error al obtener datos para firmar: Error en get_data_to_sign_tapir_jades"}), 500
        data_to_sign_bytes = data_to_sign_response["bytes"]
        signature_value, code = get_signature_value_own(data_to_sign_bytes)
        if code != 200:
            return jsonify({"status": False, "message": "Error al obtener valor de firma: Error en get_signature_value_own"}), 500
        signed_json_response, code = sign_document_tapir_jades(json, signature_value, certificates, current_time, role)
        if code == 500:
            return jsonify({"status": False, "message": "Error al firmar documento: Error en sign_document_tapir_jades"}), 500
        return signed_json_response['bytes'], 200
    except PDFSignatureError as e:
        return jsonify({"status": "error", "message": "Error en sign_own_jades: " + str(e)}), 500

##################################################
###       Función para firmar el PDF con       ###
###       certificado propio del servidor      ###
##################################################
def sign_own_pdf(pdf, is_yunga_sign, field_to_sign, stamp, area, name, datetime_signed, role):
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
    global current_time, isclosing, encoded_image

    def create_and_sign(pdf, certificates, field_to_sign, role, custom_image):
        data_to_sign_response, code = get_data_to_sign_own(pdf, certificates, current_time, field_to_sign, role, custom_image)
        if code != 200:
            return None, jsonify({"status": False, "message": "Error al obtener datos para firmar"}), 500
        data_to_sign = data_to_sign_response["bytes"]
        signature_value, code = get_signature_value_own(data_to_sign)
        if code != 200:
            return None, jsonify({"status": False, "message": "Error al obtener valor de firma"}), 500
        signed_pdf_response, code = sign_document_own(pdf, signature_value, certificates, current_time, field_to_sign, role, custom_image)
        if code != 200:
            return None, jsonify({"status": False, "message": "Error al firmar documento"}), 500
        return signed_pdf_response['bytes'], None, 200

    try:
        # Parse datetime from Y-m-d H:M:S to d/m/Y H:M:S format
        try:
            dt = datetime.strptime(datetime_signed, "%Y-%m-%d %H:%M:%S")
            datetime_signed = dt.strftime("%d/%m/%Y %H:%M:%S")
        except ValueError as e:
            return jsonify({"status": False, "message": "Error al parsear fecha y hora: " + str(e)}), 500
        if not is_yunga_sign:
            custom_image, code = create_signature_image(f"{name}\n{datetime_signed}\n{stamp}\n{area}", encoded_image, "cert")
        else:
            custom_image, code = create_signature_image(f"Sistema Yunga TC Tucumán\n{datetime_signed}", encoded_image, "yunga")
            role = "Sistema YUNGA Tribunal de Cuentas Tucuman"
        if code != 200:
            return jsonify({"status": False, "message": "Error al crear imagen de firma"}), 500

        certificates, code = get_certificate_from_local()
        if code != 200:
            return jsonify({"status": False, "message": "Error al obtener certificado local"}), 500

        signed_pdf_base64, error_response, status_code = create_and_sign(pdf, certificates, field_to_sign, role, custom_image)
        if error_response:
            return error_response, status_code

        return signed_pdf_base64, 200
    except PDFSignatureError as e:
        return jsonify({"status": "error", "message": "Error en sign: " + str(e)}), 500

##################################################
###         Función para cerrar el PDF         ###
##################################################
def close_pdf(pdf_to_close, json_field_values):
    """
    Cierra el PDF.

    Args:
        pdf_to_close (str): Base64 encoded PDF to close.
        json_field_values (str): JSON string of field values.

    Returns:
        str: Base64 encoded closed PDF.
        int: HTTP status code.
    """
    try:
        data = {
            'fileBase64': pdf_to_close,
            'fileName': "documento.pdf",
            'fieldValues': json_field_values
        }
        response = requests.post('http://java-webapp:5555/pdf/update', headers={'Content-Type': 'application/json'}, data=json.dumps(data))
        response.raise_for_status()
        signed_pdf_base64 = base64.b64encode(response.content).decode("utf-8")
        return signed_pdf_base64, 200
    except PDFSignatureError as e:
        return jsonify({"status": "error", "message": "Error cerrando el PDF: " + str(e)}), 500
    except Exception as e:
        logging.error("Unexpected error in close_pdf: %s", str(e))
        return jsonify({"status": "error", "message": "An unexpected error occurred in close_pdf"}), 500

###################################################
###      Función para obtener el número de      ###
###         cierre y la fecha de cierre         ###
###################################################
def get_number_and_date_then_close(pdf_to_close, id_doc):
    """
    Get the closing number and date, then close the PDF.

    Args:
        pdf_to_close (str): Base64 encoded PDF to close.
        id_doc (int): Document ID.

    Returns:
        str: Base64 encoded closed PDF.
        int: HTTP status code.
    """
    global conn
    dbname = os.getenv('DB_NAME')
    user = os.getenv('DB_USER')
    password = os.getenv('DB_PASSWORD')
    host = os.getenv('DB_HOST')
    port = os.getenv('DB_PORT')

    conn_params = {
        'dbname': dbname,
        'user': user,
        'password': password,
        'host': host,
        'port': port
    }
    try:
        try:
            conn = psycopg2.connect(**conn_params)
        except Exception as e:
            return jsonify({"status": "error", "message": "Error al conectar a la base de datos: " + str(e)}), 500
        if conn and conn.closed == 0:
            cursor = conn.cursor()
        try:
            cursor.execute("SELECT f_documento_protocolizar(%s)", (id_doc,))
            datos = cursor.fetchone()
            datos_json = json.loads(json.dumps(datos[0]))
            json_field_values1 = {
                "numero": datos_json['numero'],
                "fecha": datetime.strptime(datos_json['fecha'], '%Y-%m-%d').strftime('%d/%m/%Y')
            }
            json_field_values = json.dumps(json_field_values1)
            if not datos_json['status']:
                raise Exception("Error al obtener fecha y numero: " + datos_json['message'])
            try:
                pdf, code = close_pdf(pdf_to_close, json_field_values)
                if code == 500:
                    response = pdf.get_json()
                    if response['status'] == "error":
                        conn.rollback()
                        return jsonify({"status": "error", "message": "Error al cerrar PDF: " + response['message']}), 500
            except Exception as e:
                conn.rollback()
                return jsonify({"status": "error", "message": "Error al cerrar PDF: " + str(e)}), 500
            return pdf, 200
        except Exception as e:
            conn.rollback()
            return jsonify({"status": "error", "message": "Error transaccion: " + str(e)}), 500
        finally:
            cursor.close()
    except Exception as e:
        return jsonify({"status": "error", "message": "Error al conectar a la base de datos: " + str(e)}), 500

###################################################
###    Funcion para desbloquear el documento    ###
###       cerrar la tarea y guardar hash        ###
###################################################
def unlock_pdf_and_close_task(id_doc, id_user, hash_doc, is_closed, id_sello, id_oficina, tipo_firma, is_signed=1):
    """
    Unlock the PDF, close the task, and save the hash.

    Args:
        id_doc (int): Document ID.
        id_user (int): User ID.
        hash_doc (str): Document hash.
        is_closed (bool): Flag indicating if the document is closed.
        id_sello (int): Seal ID.
        id_oficina (int): Office ID.
        tipo_firma (int): Type of signature.
        is_signed (int, optional): Flag indicating if the document is signed. Defaults to 1.

    Returns:
        Response: JSON response indicating success or failure.
    """
    global conn
    dbname = os.getenv('DB_NAME')
    user = os.getenv('DB_USER')
    password = os.getenv('DB_PASSWORD')
    host = os.getenv('DB_HOST')
    port = os.getenv('DB_PORT')
    conn_params = {
        'dbname': dbname,
        'user': user,
        'password': password,
        'host': host,
        'port': port
    }
    try:
        if conn and conn.closed == 0:
            cursor = conn.cursor()
        else:
            try:
                conn = psycopg2.connect(**conn_params)
                cursor = conn.cursor()
            except Exception as e:
                return jsonify({"status": "error", "message": "Error al conectar a la base de datos: " + str(e)}), 500
    except psycopg2.InterfaceError as e:
        try:
            conn = psycopg2.connect(**conn_params)
            cursor = conn.cursor()
        except Exception as exc:
            return jsonify({"status": "error", "message": "Error al conectar a la base de datos: " + str(exc)}), 500
    try:
        cursor.execute("SELECT f_finalizar_proceso_firmado_v2 (%s, %s, %s, %s, %s, %s, %s, %s)", (id_doc, id_user, is_signed, is_closed, id_sello, id_oficina, tipo_firma, hash_doc,))
        cursor.close()
        return jsonify({"status": "success", "message": "Proceso finalizado correctamente"}), 200
    except Exception as e:
        conn.rollback()
        cursor.close()
        conn.close()
        return jsonify({"status": "error", "message": "Error transaccion finalizar proceso: " + str(e)}), 500

##################################################
##################################################
###     Rutas de la aplicacion para Tapir      ###
##################################################
##################################################

#1  ##################################################
    ###   Ruta de inicio de proceso firma digital, ###
    ###   o proceso completo de firma electronica  ###
    ##################################################
@app.route('/firmalote', methods=['POST'])
def firmalote():
    """
    Route for batch signing process or complete electronic signing process.
    """
    global current_time, datetimesigned, conn, encoded_image, isclosing
    try:
        data = request.get_json()
        pdfs = data['pdfs']
        certificates = data['certificates']
    except Exception as e:
        return jsonify({"status": False, "message": "Error al obtener los datos de la request: " + str(e)}), 500

    id_docs_signeds = []
    errors_stack = []
    data_to_sign = []

    current_time = int(tiempo.time() * 1000)
    datetimesigned = datetime.now(pytz.utc).astimezone(pytz.timezone('America/Argentina/Buenos_Aires')).strftime("%Y-%m-%d %H:%M:%S")

    for pdf in pdfs:
        try:
            pdf_b64 = pdf['pdf']

            field_id = pdf['firma_lugar']
            name = pdf['firma_nombre']
            stamp = pdf['firma_sello']
            area = pdf['firma_area']

            id_sello = pdf['id_sello']
            id_oficina = pdf['id_oficina']

            isclosing = pdf['firma_cierra']
            closingplace = pdf['firma_lugarcierre']
            id_doc = pdf['id_doc']
            isdigital = pdf['firma_digital']

            id_user = pdf['id_usuario']
            filepath = pdf['path_file']

            es_caratula = pdf.get('es_caratula', False)

            if isdigital:
                name, code = extract_certificate_info_name(certificates['certificate'])
                if code != 200:
                    errors_stack.append({"idDocFailed": id_doc, "message": "Error al extraer nombre del certificado"})
                    raise PDFSignatureError("Error al extraer nombre del certificado")

            role = name + ", " + stamp + ", " + area

            if isdigital:
                dt = datetime.strptime(datetimesigned, "%Y-%m-%d %H:%M:%S")
                datetimesigned = dt.strftime("%d/%m/%Y %H:%M:%S")
                custom_image, code = create_signature_image(
                                f"{name}\n{datetimesigned}\n{stamp}\n{area}",
                                encoded_image,
                                "token"
                            )
                if code != 200:
                    errors_stack.append({"idDocFailed": id_doc, "message": "Error al crear imagen de firma"})
                    raise PDFSignatureError("Error al crear imagen de firma")

            match (isdigital, isclosing):
                case (True, True):
                    data_to_sign_response, code = get_data_to_sign_tapir(pdf_b64, certificates, current_time, field_id, role, custom_image)
                    if code == 500:
                        errors_stack.append({"idDocFailed": id_doc, "message": "Error al obtener datos para firmar: Error en get_data_to_sign_tapir"})
                        raise PDFSignatureError("Error al obtener datos para firmar: Error en get_data_to_sign_tapir")
                    data_to_sign_bytes = data_to_sign_response["bytes"]
                    data_to_sign.append(data_to_sign_bytes)

                case (True, False):
                    data_to_sign_response, code = get_data_to_sign_tapir(pdf_b64, certificates, current_time, field_id, role, custom_image)
                    if code == 500:
                        errors_stack.append({"idDocFailed": id_doc, "message": "Error al obtener datos para firmar: Error en get_data_to_sign_tapir"})
                        raise PDFSignatureError("Error al obtener datos para firmar: Error en get_data_to_sign_tapir")
                    data_to_sign_bytes = data_to_sign_response["bytes"]
                    data_to_sign.append(data_to_sign_bytes)

                case (False, True):
                    signed_pdf_base64, code = sign_own_pdf(pdf_b64, False, field_id, stamp, area, name, datetimesigned, role)
                    if code != 200:
                        errors_stack.append({"idDocFailed": id_doc, "message": "Error al firmar PDF: Error en sign_own_pdf"})
                        raise PDFSignatureError("Error al firmar PDF: Error en sign_own_pdf")
                    if not es_caratula:
                        lastpdf, code = get_number_and_date_then_close(signed_pdf_base64, id_doc)
                        if code == 500:
                            response = lastpdf.get_json()
                            if response['status'] == "error":
                                errors_stack.append({"idDocFailed": id_doc, "message": "Error al cerrar PDF: Error en get_number_and_date_then_close"})
                                raise PDFSignatureError("Error al cerrar PDF: Error en get_number_and_date_then_close")
                    else:
                        lastpdf = signed_pdf_base64
                    signed_pdf_base64_closed, code = sign_own_pdf(lastpdf, True, closingplace, stamp, area, name, datetimesigned, role)
                    if code != 200:
                        errors_stack.append({"idDocFailed": id_doc, "message": "Error al firmar PDF: Error en sign_own_pdf"})
                        raise PDFSignatureError("Error al firmar PDF: Error en sign_own_pdf")
                    finalpdf = signed_pdf_base64_closed
                    is_closed = True

                case (False, False):
                    signed_pdf_base64, code = sign_own_pdf(pdf_b64, False, field_id, stamp, area, name, datetimesigned, role)
                    if code != 200:
                        errors_stack.append({"idDocFailed": id_doc, "message": "Error al firmar PDF: Error en sign_own_pdf"})
                        raise PDFSignatureError("Error al firmar PDF: Error en sign_own_pdf")
                    finalpdf = signed_pdf_base64
                    is_closed = False

            tipo_firma = 2 if isdigital else 1

            if not isdigital:
                hash_object = hashlib.sha256(io.BytesIO(base64.b64decode(finalpdf)).getvalue())
                hash_doc = hash_object.hexdigest()

                message, code = unlock_pdf_and_close_task(id_doc, id_user, hash_doc, is_closed, id_sello, id_oficina, tipo_firma)
                if code != 200:
                    errors_stack.append({"idDocFailed": id_doc, "message": "Error en unlock_pdf_and_close_task" + str(message)})
                    raise PDFSignatureError("Error en unlock_pdf_and_close_task")

                message, code = save_signed_pdf(finalpdf, filepath)
                if code != 200:
                    errors_stack.append({"idDocFailed": id_doc, "message": "Error al guardar PDF firmado" + str(message)})
                    raise PDFSignatureError("Error al guardar PDF firmado")
                id_docs_signeds.append(id_doc)

        except PDFSignatureError as e:
            if conn and conn.closed == 0:
                conn.rollback()
                conn.close()
        if conn and conn.closed == 0:
            conn.commit()
            conn.close()

    docs_not_signed = []
    for error in errors_stack:
        docs_not_signed.append(error['idDocFailed'])

    return jsonify({"status": True, "docsSigned": id_docs_signeds, "docsNotSigned": docs_not_signed, "dataToSign": data_to_sign}), 200

#2  ##################################################
    ###     Ruta de completado del proceso de      ###
    ###               firma digital                ###
    ##################################################
@app.route('/firmaloteend', methods=['POST'])
def firmaloteend():
    """
    Route for completing the digital signing process.
    """
    global current_time, datetimesigned, conn, encoded_image, isclosing
    try:
        data = request.get_json()
        pdfs = data['pdfs']
        certificates = data['certificates']
    except Exception as e:
        return jsonify({"status": False, "message": "Error al obtener los datos de la request: " + str(e)}), 500

    id_docs_signeds = []
    errors_stack = []

    for pdf in pdfs:
        try:
            pdf_b64 = pdf['pdf']

            field_id = pdf['firma_lugar']
            name = pdf['firma_nombre']
            stamp = pdf['firma_sello']
            area = pdf['firma_area']

            id_sello = pdf['id_sello']
            id_oficina = pdf['id_oficina']

            isclosing = pdf['firma_cierra']
            closingplace = pdf['firma_lugarcierre']
            id_doc = pdf['id_doc']
            isdigital = pdf['firma_digital']

            signature_value = pdf['signatureValue']
            id_user = pdf['id_usuario']
            filepath = pdf['path_file']

            if isdigital:
                name, code = extract_certificate_info_name(certificates['certificate'])
                if code != 200:
                    errors_stack.append({"idDocFailed": id_doc, "message": "Error al extraer nombre del certificado"})
                    raise PDFSignatureError("Error al extraer nombre del certificado")

            role = name + ", " + stamp + ", " + area

            if isdigital:
                dt = datetime.strptime(datetimesigned, "%Y-%m-%d %H:%M:%S")
                datetimesigned = dt.strftime("%d/%m/%Y %H:%M:%S")
                custom_image, code = create_signature_image(
                                f"{name}\n{datetimesigned}\n{stamp}\n{area}",
                                encoded_image,
                                "token"
                            )
                if code != 200:
                    errors_stack.append({"idDocFailed": id_doc, "message": "Error al crear imagen de firma"})
                    raise PDFSignatureError("Error al crear imagen de firma")

            match (isdigital, isclosing):
                case (True, True):
                    signed_pdf_response, code = sign_document_tapir(pdf_b64, signature_value, certificates, current_time, field_id, role, custom_image)
                    if code == 500:
                        errors_stack.append({"idDocFailed": id_doc, "message": "Error al firmar PDF: Error en sign_document_tapir"})
                        raise PDFSignatureError("Error al firmar PDF: Error en sign_document_tapir")
                    signed_pdf_base64 = signed_pdf_response['bytes']
                    lastpdf, code = get_number_and_date_then_close(signed_pdf_base64, id_doc)
                    if code == 500:
                        response = lastpdf.get_json()
                        if response['status'] == "error":
                            errors_stack.append({"idDocFailed": id_doc, "message": "Error al cerrar PDF: Error en get_number_and_date_then_close"})
                            raise PDFSignatureError("Error al cerrar PDF: Error en get_number_and_date_then_close")
                    lastsignedpdf, code = sign_own_pdf(lastpdf, True, closingplace, stamp, area, name, datetimesigned, None)
                    if code != 200:
                        errors_stack.append({"idDocFailed": id_doc, "message": "Error al firmar PDF: Error en sign_own_pdf"})
                        raise PDFSignatureError("Error al firmar PDF: Error en sign_own_pdf")
                    finalpdf = lastsignedpdf
                    is_closed = True
                    id_docs_signeds.append(id_doc)

                case (True, False):
                    signed_pdf_response, code = sign_document_tapir(pdf_b64, signature_value, certificates, current_time, field_id, role, custom_image)
                    if code == 500:
                        errors_stack.append({"idDocFailed": id_doc, "message": "Error al firmar PDF: Error en sign_document_tapir"})
                        raise PDFSignatureError("Error al firmar PDF: Error en sign_document_tapir")
                    signed_pdf_base64 = signed_pdf_response['bytes']
                    finalpdf = signed_pdf_base64
                    is_closed = False
                    id_docs_signeds.append(id_doc)

            hash_object = hashlib.sha256(io.BytesIO(base64.b64decode(finalpdf)).getvalue())
            hash_doc = hash_object.hexdigest()

            tipo_firma = 2 if isdigital else 1

            message, code = unlock_pdf_and_close_task(id_doc, id_user, hash_doc, is_closed, id_sello, id_oficina, tipo_firma)
            if code != 200:
                errors_stack.append({"idDocFailed": id_doc, "message": "Error en unlock_pdf_and_close_task" + str(message)})
                raise PDFSignatureError("Error en unlock_pdf_and_close_task")

            message, code = save_signed_pdf(finalpdf, filepath)
            if code != 200:
                errors_stack.append({"idDocFailed": id_doc, "message": "Error al guardar PDF firmado" + str(message)})
                raise PDFSignatureError("Error al guardar PDF firmado")
            id_docs_signeds.append(id_doc)

        except PDFSignatureError as e:
            if conn and conn.closed == 0:
                conn.rollback()
                conn.close()
        if conn and conn.closed == 0:
            conn.commit()
            conn.close()

    docs_not_signed = []
    for error in errors_stack:
        docs_not_signed.append(error['idDocFailed'])

    return jsonify({"status": True, "docsSigned": id_docs_signeds, "docsNotSigned": docs_not_signed}), 200

#3  ##################################################
    ###   Ruta de validacion de indices en json    ###
    ##################################################
@app.route('/validarjades', methods=['POST'])
def validarjades():
    """
    Route for validating JADES signatures.
    """
    try:
        data_original = request.get_json()

        # List to store validation results
        validation_results = []
        data = copy.deepcopy(data_original)

        # Iterate through tramites in reverse order
        for tramite in reversed(data['tramites']):
            # Extract and remove the signature from the current tramite
            try:
                signature = tramite.pop('firma', '')
                if not signature or signature == '' or signature is None:
                    raise PDFSignatureError("Error al obtener la firma del tramite. Posiblemente el tramite no se haya firmado")
            except Exception as e:
                return jsonify({"status": False, "message": "Error al obtener la firma del tramite: " + str(e)}), 500

            json_str = copy.deepcopy(data)

            # Validate the signature
            valid, code = validate_signature(json_str, signature)
            if code != 200:
                raise PDFSignatureError("Error en validate_signature")

            validation_result, code = validation_analyze(valid)
            if code != 200:
                raise PDFSignatureError("Error en validation_analyze")

            tested = bool(validation_result[0]['valid'])

            certs_validation = validation_result[0]['certs_valid']

            indication = True if certs_validation and tested else False

            validation_results.append({
                'secuencia': tramite['secuencia'],
                'is_valid': tested,
                'certs_valid': certs_validation,
                'subindication': indication,
                'signature': validation_result
            })

            data['tramites'].remove(tramite)

        # Reverse the validation results to match the original order
        validation_results.reverse()
        validation = {}
        validation['subresults'] = validation_results

        for result in validation_results:
            total = bool(result['subindication'])
            if not total:
                break

        validation['conclusion'] = total

        return jsonify({
            "status": True,
            "original_data": data_original,
            "validation": validation
        }), 200

    except Exception as e:
        return jsonify({"status": False, "message": f"Error processing request: {str(e)}"}), 500

#4  ##################################################
    ###   Ruta de firma de documentos con JADES    ###
    ###   Inicio de proceso digital y proceso      ###
    ###       electronico completo de firma        ###
    ##################################################
@app.route("/firmajades", methods=["POST"])
def signjades():
    """
    Route for signing documents using JADES.
    """
    global current_time
    try:
        data = request.get_json()
        certificates = data['certificates']
        indexes_data = data['indices']
        data_signature = data['datos_firma']
    except Exception as e:
        return jsonify({"status": False, "message": "Error al obtener los datos de la request: " + str(e)}), 500
    
    id_exps_signeds = []
    errors_stack = []
    data_to_sign = []
    index_signeds = []

    current_time = int(tiempo.time() * 1000)

    for index_data in indexes_data:
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
                name, code = extract_certificate_info_name(certificates['certificate'])
                if code != 200:
                    errors_stack.append({"idExpFailed": f"{index['numero']}/{index['anio']}/{index['codigo']}/{index['letra']}", "message": "Error al extraer nombre del certificado"})
                    raise PDFSignatureError("Error al extraer nombre del certificado")
            
            role = name + ", " + stamp + ", " + area

            if isdigital:
                data_to_sign_response, code = get_data_to_sign_tapir_jades(jsonb64, certificates, current_time, role)
                if code == 500:
                    errors_stack.append({"idExpFailed": f"{index['numero']}/{index['anio']}/{index['codigo']}/{index['letra']}", "message": "Error al obtener datos para firmar: Error en get_data_to_sign_tapir_jades"})
                    raise PDFSignatureError("Error al obtener datos para firmar: Error en get_data_to_sign_tapir_jades")
                data_to_sign_bytes = data_to_sign_response["bytes"]
                data_to_sign.append(data_to_sign_bytes)
            
            else:
                signed_json_b64, code = sign_own_jades(jsonb64, role)
                if code != 200:
                    errors_stack.append({"idExpFailed": f"{index['numero']}/{index['anio']}/{index['codigo']}/{index['letra']}", "message": "Error al firmar documento: Error en sign_own_jades"})
                    raise PDFSignatureError("Error al firmar documento: Error en sign_own_jades")
                tramite['firma'] = signed_json_b64

            if not isdigital:
                id_exps_signeds.append(f"{index['numero']}/{index['anio']}/{index['codigo']}/{index['letra']}")
                index_signeds.append(index)

        
        except Exception as e:
            continue
        
    exps_not_signed = []
    for error in errors_stack:
        exps_not_signed.append(error['idExpFailed'])

    return jsonify({"status": True, "expsSigned": id_exps_signeds, "expsNotSigned": exps_not_signed, "dataToSign": data_to_sign, "indexSigneds": index_signeds}), 200

#5  ##################################################
    ###      Ruta de completado del proceso de     ###
    ###             firma digital JSON             ###
    ##################################################
@app.route('/firmajadesend', methods=['POST'])
def signjadesend():
    """
    Route for completing the JADES signing process.
    """
    global current_time
    try:
        data = request.get_json()
        certificates = data['certificates']
        indexes_data = data['indices']
        data_signature = data['datos_firma']
    except Exception as e:
        return jsonify({"status": False, "message": "Error al obtener los datos de la request: " + str(e)}), 500
    
    id_exps_signeds = []
    errors_stack = []
    index_signeds = []
    
    for index_data in indexes_data:
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
                name, code = extract_certificate_info_name(certificates['certificate'])
                if code != 200:
                    errors_stack.append({"idExpFailed": f"{index['numero']}/{index['anio']}/{index['codigo']}/{index['letra']}", "message": "Error al extraer nombre del certificado"})
                    raise PDFSignatureError("Error al extraer nombre del certificado")
                
            role = name + ", " + stamp + ", " + area

            if isdigital:
                signed_json_response, code = sign_document_tapir_jades(jsonb64, signature, certificates, current_time, role)
                if code == 500:
                    errors_stack.append({"idExpFailed": f"{index['numero']}/{index['anio']}/{index['codigo']}/{index['letra']}", "message": "Error al firmar documento: Error en sign_document_tapir_jades"})
                    raise PDFSignatureError("Error al firmar documento: Error en sign_document_tapir_jades")
                signed_json_b64 = signed_json_response['bytes']
                tramite['firma'] = signed_json_b64

            id_exps_signeds.append(f"{index['numero']}/{index['anio']}/{index['codigo']}/{index['letra']}")
            index_signeds.append(index)

        except Exception as e:
            continue
    
    exps_not_signed = []
    for error in errors_stack:
        exps_not_signed.append(error['idExpFailed'])

    return jsonify({"status": True, "expsSigned": id_exps_signeds, "expsNotSigned": exps_not_signed, "indexSigneds": index_signeds}), 200  

#6  ##################################################
    ###      Ruta de validacion de PDFs            ###
    ##################################################
@app.route('/validatepdfs', methods=['POST'])
def validatepdfs():
    """
    Route for validating PDFs.
    """
    try:
        data = request.get_json()
        pdfs = data['pdfs']
    except Exception as e:
        return jsonify({"status": False, "message": "Error al obtener los datos de la request: " + str(e)}), 500
    
    results = []
    for pdf in pdfs:
        try:
            pdf_b64 = pdf['pdf']
            id_doc = pdf['id_documento']
            report, code = validate_signature(None, pdf_b64)
            if code != 200:
                raise PDFSignatureError("Error al validar PDF: Error en validate_pdf: id_doc: " + id_doc)
            signatures, code = validation_analyze(report)
            if code != 200:
                raise PDFSignatureError("Error al validar PDF: Error en validation_analyze: id_doc: " + id_doc)
            results.append({
                "id_documento": id_doc,
                "signatures": signatures
            })
        except PDFSignatureError as e:
            return jsonify({"status": False, "message": "Error al validar PDFs: " + str(e)}), 500
    return jsonify({"status": True, "pdfs": results}), 200

#7  ##################################################
    ###   Ruta de validación de expediente (ZIP)   ###
    ##################################################
from concurrent.futures import ThreadPoolExecutor, as_completed
import multiprocessing
import re

cpu_count = multiprocessing.cpu_count()
max_workers = cpu_count * 2/3  # Adjust based on testing

def process_document(doc, files, doc_order_to_filename):
    doc_hash = doc['hash_contenido']
    doc_id = doc['id_documento']
    doc_order = str(doc['orden'])
    result_doc = {
        "orden": doc['orden'],
        "id_documento": doc_id,
        "valid_hash": False,
        "doc_filename": None,
        "signatures": None,
        "not_found": False
    }
    try:
        if doc_order in doc_order_to_filename:
            doc_filename = doc_order_to_filename[doc_order]
            doc_content = files[doc_filename]
            docb64 = base64.b64encode(doc_content).decode('utf-8')

            # Validate the document
            report, code = validate_signature(None, docb64)
            if code != 200:
                raise Exception(f"Error al validar PDF: Error en validate_signature: id_doc: {doc_id}")
            signatures, code = validation_analyze(report)
            if code != 200:
                raise Exception(f"Error al validar PDF: Error en validation_analyze: id_doc: {doc_id}")
            hash_doc = hashlib.sha256(doc_content).hexdigest()
            if not doc_hash:
                valid_hash = False
            else:
                valid_hash = (hash_doc == doc_hash.lower())

            result_doc.update({
                "valid_hash": valid_hash,
                "doc_filename": doc_filename,
                "signatures": signatures
            })
        else:
            result_doc['not_found'] = True
    except Exception as e:
        result_doc['error'] = str(e)
    return result_doc

def process_tramite(index, json_str, signature, tramite, files, doc_order_to_filename, max_workers):
    result = {}
    try:

        # Validate the signature using the prepared json_str and signature
        valid, code = validate_signature(json_str, signature)
        if code != 200:
            return {"error": "Error en validate_signature"}

        validation_result, code = validation_analyze(valid)
        if code != 200:
            return {"error": "Error en validation_analyze"}

        tested = bool(validation_result[0]['valid'])
        certs_validation = validation_result[0]['certs_valid']

        docs_validation = []
        docs_not_found = []
        errors = []

        # Process documents in parallel using threads
        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            results = executor.map(
                lambda doc: process_document(doc, files, doc_order_to_filename),
                tramite['documentos']
            )

        for result_doc in results:
            docs_validation.append(result_doc)
            if result_doc.get('not_found', False):
                docs_not_found.append({
                    "id_documento": result_doc['id_documento'],
                    "orden": result_doc['orden']
                })
            if 'error' in result_doc:
                errors.append(result_doc['error'])

        # Handle errors if any
        if errors:
            return {"error": errors[0]}  # or handle multiple errors

        # Proceed with the rest of your code
        hashes_valid = []
        hashes_invalid = []
        for doc in docs_validation:
            if not doc['valid_hash']:
                hashes_invalid.append({"id_documento": doc['id_documento'], "orden": doc['orden']})
            else:
                hashes_valid.append({"id_documento": doc['id_documento'], "orden": doc['orden']})

        if not tested:
            if certs_validation:
                indication = "Tramite invalido: firma invalida." + " Documentos con hash invalido: " + (str(hashes_invalid) if hashes_invalid else "ninguno")
                result_indication = False
            else:
                indication = "Tramite invalido: firma invalida y certificados invalidos." + " Documentos con hash invalido: " + (str(hashes_invalid) if hashes_invalid else "ninguno")
                result_indication = False
        else:
            if not certs_validation:
                indication = "Tramite invalido: certificados invalidos." + " Documentos con hash invalido: " + (str(hashes_invalid) if hashes_invalid else "ninguno")
                result_indication = False
            else:
                if hashes_invalid:
                    indication = "Tramite invalido: documentos con hash invalido: " + str(hashes_invalid)
                    result_indication = False
                else:
                    indication = "Tramite valido"
                    result_indication = True

        result = {
            'secuencia': tramite['secuencia'],
            'is_valid': tested,
            'certs_valid': certs_validation,
            'signature': validation_result,
            'docs_validation': docs_validation,
            'docs_not_found': docs_not_found,
            'subindication': indication,
            'result_indication': result_indication
        }
        return result

    except Exception as e:
        return {"error": str(e)}

@app.route('/validar_expediente', methods=['POST'])
def validate_expediente():
    """
    Route for validating an entire set of documents (expediente) in compressed format.
    """
    try:
        data = request.get_json()
        file_path = data.get('zip_filepath')
        path = "/app/expedientes/" + file_path
        if not file_path or not os.path.exists(path):
            return jsonify({"status": False, "message": "Archivo no encontrado " + path}), 400
        import unicodedata
        try:
            # Extract all files from the archive once
            files = {}
            doc_order_to_filename = {}
            pdf_count = 0
            with libarchive.file_reader(path) as archive:
                for entry in archive:
                    # Skip directory entries
                    if entry.isdir:
                        continue
                        
                    # Decode the pathname if necessary
                    entry_pathname = entry.pathname
                    if isinstance(entry_pathname, bytes):
                        try:
                            entry_pathname = entry_pathname.decode('utf-8')
                        except UnicodeDecodeError:
                            entry_pathname = entry_pathname.decode('latin-1')

                    # Normalize to handle inconsistencies and remove accents or invalid characters
                    entry_path = unicodedata.normalize('NFKD', entry_pathname).encode('ascii', 'ignore').decode('ascii')

                    # Normalize the pathname to handle inconsistencies
                    normalized_path = os.path.normpath(entry_path)

                    # Use os.path.basename to get the filename
                    file_name = os.path.basename(normalized_path)

                    # Now file_name should be just the filename without any directory components
                    content = b''.join(entry.get_blocks())
                    files[file_name] = content

                    if file_name.lower().endswith('.pdf'):
                        pdf_count += 1
                        base_name = os.path.splitext(file_name)[0]
                        # Use regex to extract the order number after the first underscore
                        match = re.match(r'[^_]+_([^_]+)_?', base_name)
                        if match:
                            doc_order = match.group(1)
                            print(file_name)
                            doc_order_to_filename[doc_order] = file_name
                        else:
                            # Handle error if order number is not found
                            print(f"Warning: Could not extract order number from filename: {file_name}")

            # Find index_json
            index_json = None
            for filename, content in files.items():
                if filename[-5:] == '.json':
                    try:
                        index_json = json.loads(content.decode('utf-8'))
                        break  # Exit after finding the first JSON file
                    except json.JSONDecodeError:
                        return jsonify({"status": False, "message": f"{filename} no es un JSON válido"}), 400
            if index_json is None:
                return jsonify({"status": False, "message": "No se encontró ningún archivo JSON en el archivo"}), 400

            # Count total documents in index_json
            total_docs_in_index = sum(len(tramite['documentos']) for tramite in index_json['tramites'])

            validation_results = []
            tramites = index_json['tramites']

            # Prepare arguments for each tramite
            tramite_args = []
            tramites_processed = []

            for idx, tramite in enumerate(tramites):
                tramite_copy = copy.deepcopy(tramite)
                signature = tramite_copy.pop('firma', '')
                if not signature:
                    return jsonify({"status": False, "message": "Error al obtener la firma del tramite. Posiblemente el tramite no se haya firmado"}), 500

                # Build 'json_str' with tramites up to and including the current one, without the current 'firma'
                tramites_to_include = tramites_processed + [tramite_copy]
                json_str = copy.deepcopy(index_json)
                json_str['tramites'] = tramites_to_include

                # Append the original tramite (with 'firma') to 'tramites_processed' for the next iteration
                tramites_processed.append(tramite)

                # Prepare arguments for process_tramite
                tramite_args.append((idx, json_str, signature, tramite_copy, files, doc_order_to_filename, max_workers))

            # Process tramites in parallel using threads
            with ThreadPoolExecutor(max_workers=max_workers) as executor:
                futures = {
                    executor.submit(process_tramite, *args): idx
                    for idx, args in enumerate(tramite_args)
                }
                results_dict = {}
                for future in futures:
                    idx = futures[future]
                    result = future.result()
                    if 'error' in result:
                        return jsonify({"status": False, "message": result['error']}), 500
                    results_dict[idx] = result

            # Collect results in order
            validation_results = [results_dict[idx] for idx in range(len(tramites))]

            # No need to reverse since we're processing in order
            validation = {'subresults': validation_results}

            total = all(result['result_indication'] for result in validation_results)
            validation['conclusion'] = total

            # Check for any extra files after processing
            if len(files) - 1 > total_docs_in_index:
                validation['conclusion'] = False
                validation['message'] = f"El archivo ZIP contiene más archivos ({len(files) - 1}) que los documentos declarados en el índice ({total_docs_in_index}). Esto puede incluir PDFs adicionales u otros tipos de archivos no permitidos."

            return jsonify({
                "status": True,
                "validation": validation
            }), 200

        except libarchive.exception.ArchiveError as e:
            return jsonify({"status": False, "message": f"Error al leer el archivo: {str(e)}"}), 500
        except Exception as e:
            return jsonify({"status": False, "message": f"Error inesperado al procesar el archivo: {str(e)}"}), 500

    except Exception as e:
        return jsonify({"status": False, "message": f"Error al procesar el expediente: {str(e)}"}), 500
    
#8  ##################################################
    ###             Ruta de testeo                 ###
    ##################################################
@app.route('/test', methods=['GET', 'POST'])
def test_route():
    """
    Test route.
    """
    return jsonify({"status": "success", "message": "Test route"}), 200


#9  ##################################################
    ###         Concatenar y Watermark PDFs        ###
    ##################################################
@app.route('/concatenarpdfs', methods=['POST'])
def mergepdfs():
    
    try:
        start_time = time()
        raw_data = request.get_json()
        pdfs_base64 = raw_data['pdfs']
        texto_marca_agua = raw_data['texto_marca_agua']

        try:
            pdfs_bytes = [base64.b64decode(pdf) for pdf in pdfs_base64]
        except Exception as e:
            return jsonify({"status": False, "message": f"Error al decodificar los PDFs: {str(e)}"}), 500
        
        pdf_merged = merge_pdf_files_pdfrw(pdfs_bytes)
        watermark_text = f"Descargado por: {texto_marca_agua} {datetime.now().strftime('%d/%m/%Y-%H:%M:%S')}"
        watermarked_pdf = add_watermark_to_pdf(pdf_merged, watermark_text)
        watermarked_pdf_base64 = base64.b64encode(watermarked_pdf).decode('utf-8')
        end_time = time()
        processing_time = end_time - start_time
        print(f"Tiempo de concatenacion y watermarking: {processing_time:.4f} segundos")
        
        return jsonify({
            "status": True,
            "Time": f"Tiempo de concatenacion y watermarking: {processing_time:.4f} segundos",
            "message": "PDFs concatenados correctamente",
            "output_pdf": watermarked_pdf_base64
        }), 200
    
    except KeyError as e:
        return jsonify({"status": False, "message": f"Error: Falta el campo {str(e)} en la solicitud"}), 400
    except Exception as e:
        return jsonify({"status": False, "message": f"Error: {str(e)}"}), 500