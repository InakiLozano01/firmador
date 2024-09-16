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
import pytz
import psycopg2
from dotenv import load_dotenv
import requests
from flask import Flask, request, jsonify

##################################################
###              Imports propios               ###
##################################################
from dss_sign import get_data_to_sign_own, sign_document_own, get_data_to_sign_tapir, sign_document_tapir, get_data_to_sign_tapir_jades, sign_document_tapir_jades
from localcerts import get_certificate_from_local, get_signature_value_own
from certificates import extract_certificate_info_name
from errors import PDFSignatureError
from imagecomp import encode_image
from createimagetostamp import create_signature_image

##################################################
###         Cargar variables de entorno        ###
##################################################
load_dotenv()

##################################################
###      Configuracion de aplicacion Flask     ###
##################################################
app = Flask(__name__)
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
'''compressedimage = compressed_image_encoded("logo_tribunal_para_tapir.png")'''


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
            f.write(signed_pdf_bytes)
        return jsonify({"status": True, "message": "PDF firmado guardado correctamente."}), 200
    except Exception as e:
        logging.error("Error in save_signed_pdf: %s", str(e))
        return jsonify({"status": False, "message": "Error al guardar el PDF firmado."}), 500

##################################################
###       Función para firmar el PDF con       ###
###       certificado propio del servidor      ###
##################################################
def sign_own_pdf(pdf, is_yunga_sign, field_to_sign, stamp, area, name, datetime_signed):
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

    def create_and_sign(pdf, certificates, field_to_sign, stamp, custom_image):
        data_to_sign_response, code = get_data_to_sign_own(pdf, certificates, current_time, field_to_sign, stamp, custom_image)
        if code != 200:
            return None, jsonify({"status": False, "message": "Error al obtener datos para firmar"}), 500
        data_to_sign = data_to_sign_response["bytes"]
        signature_value, code = get_signature_value_own(data_to_sign)
        if code != 200:
            return None, jsonify({"status": False, "message": "Error al obtener valor de firma"}), 500
        signed_pdf_response, code = sign_document_own(pdf, signature_value, certificates, current_time, field_to_sign, stamp, custom_image)
        if code != 200:
            return None, jsonify({"status": False, "message": "Error al firmar documento"}), 500
        return signed_pdf_response['bytes'], None, 200

    try:
        if not is_yunga_sign:
            custom_image, code = create_signature_image(f"{name}\n{datetime_signed}\n{stamp}\n{area}", encoded_image, "cert")
        else:
            custom_image, code = create_signature_image(f"Sistema Yunga TC Tucumán\n{datetime_signed}", encoded_image, "yunga")

        if code != 200:
            return jsonify({"status": False, "message": "Error al crear imagen de firma"}), 500

        certificates, code = get_certificate_from_local()
        if code != 200:
            return jsonify({"status": False, "message": "Error al obtener certificado local"}), 500

        signed_pdf_base64, error_response, status_code = create_and_sign(pdf, certificates, field_to_sign, stamp, custom_image)
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
        response = requests.post('http://java-webapp:5555/pdf/update', data=data)
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
                "fecha": datos_json['fecha']
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

            if isdigital:
                name, code = extract_certificate_info_name(certificates['certificate'])
                if code != 200:
                    errors_stack.append({"idDocFailed": id_doc, "message": "Error al extraer nombre del certificado"})
                    raise PDFSignatureError("Error al extraer nombre del certificado")

            if isdigital:
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
                    data_to_sign_response, code = get_data_to_sign_tapir(pdf_b64, certificates, current_time, field_id, stamp, custom_image)
                    if code == 500:
                        errors_stack.append({"idDocFailed": id_doc, "message": "Error al obtener datos para firmar: Error en get_data_to_sign_tapir"})
                        raise PDFSignatureError("Error al obtener datos para firmar: Error en get_data_to_sign_tapir")
                    data_to_sign_bytes = data_to_sign_response["bytes"]
                    data_to_sign.append(data_to_sign_bytes)

                case (True, False):
                    data_to_sign_response, code = get_data_to_sign_tapir(pdf_b64, certificates, current_time, field_id, stamp, custom_image)
                    if code == 500:
                        errors_stack.append({"idDocFailed": id_doc, "message": "Error al obtener datos para firmar: Error en get_data_to_sign_tapir"})
                        raise PDFSignatureError("Error al obtener datos para firmar: Error en get_data_to_sign_tapir")
                    data_to_sign_bytes = data_to_sign_response["bytes"]
                    data_to_sign.append(data_to_sign_bytes)

                case (False, True):
                    signed_pdf_base64, code = sign_own_pdf(pdf_b64, False, field_id, stamp, area, name, datetimesigned)
                    if code != 200:
                        errors_stack.append({"idDocFailed": id_doc, "message": "Error al firmar PDF: Error en sign_own_pdf"})
                        raise PDFSignatureError("Error al firmar PDF: Error en sign_own_pdf")
                    lastpdf, code = get_number_and_date_then_close(signed_pdf_base64, id_doc)
                    if code == 500:
                        response = lastpdf.get_json()
                        if response['status'] == "error":
                            errors_stack.append({"idDocFailed": id_doc, "message": "Error al cerrar PDF: Error en get_number_and_date_then_close"})
                            raise PDFSignatureError("Error al cerrar PDF: Error en get_number_and_date_then_close")
                    signed_pdf_base64_closed, code = sign_own_pdf(lastpdf, True, closingplace, stamp, area, name, datetimesigned)
                    if code != 200:
                        errors_stack.append({"idDocFailed": id_doc, "message": "Error al firmar PDF: Error en sign_own_pdf"})
                        raise PDFSignatureError("Error al firmar PDF: Error en sign_own_pdf")
                    finalpdf = signed_pdf_base64_closed
                    is_closed = True

                case (False, False):
                    signed_pdf_base64, code = sign_own_pdf(pdf_b64, False, field_id, stamp, area, name, datetimesigned)
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

            if isdigital:
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
                    signed_pdf_response, code = sign_document_tapir(pdf_b64, signature_value, certificates, current_time, field_id, stamp, custom_image)
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
                    lastsignedpdf, code = sign_own_pdf(lastpdf, True, closingplace, stamp, area, name, datetimesigned)
                    if code != 200:
                        errors_stack.append({"idDocFailed": id_doc, "message": "Error al firmar PDF: Error en sign_own_pdf"})
                        raise PDFSignatureError("Error al firmar PDF: Error en sign_own_pdf")
                    finalpdf = lastsignedpdf
                    is_closed = True
                    id_docs_signeds.append(id_doc)

                case (True, False):
                    signed_pdf_response, code = sign_document_tapir(pdf_b64, signature_value, certificates, current_time, field_id, stamp, custom_image)
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

def validate_signature(data, signature):
    """
    Validate the signature of a document.

    Args:
        data (str): The data to validate.
        signature (str): The signature to validate.

    Returns:
        dict: The validation result.
        int: HTTP status code.
    """
    body = {
        "signedDocument": {
            "bytes": signature,
            "digestAlgorithm": None,
            "name": "sign.json"
        },
        "originalDocuments": [{
            "bytes": base64.b64encode(json.dumps(data, separators=(',', ':'), ensure_ascii=False).encode('utf-8')).decode('utf-8') if data else None,
            "digestAlgorithm": None,
            "name": "signed.json"
        }],
        "policy": None,
        "evidenceRecords": None,
        "tokenExtractionStrategy": "NONE",
        "signatureId": None
    }

    try:
        response = requests.post('http://java-webapp:5555/services/rest/validation/validateSignature', json=body, timeout=10)
        response.raise_for_status()
        return response.json(), 200
    except Exception as e:
        return jsonify({"status": False, "message": "Error in validate_signature" + str(e)}), 500

def validation_analyze(report):
    """
    Analyze the validation report.

    Args:
        report (dict): The validation report.

    Returns:
        list: List of validation results.
        list: List of certificates.
    """
    try:
        passed = []
        certificates = []
        for signature in report['DiagnosticData']['Signature']:
            if signature['StructuralValidation']['valid'] is True and signature['BasicSignature']['SignatureIntact'] is True and signature['BasicSignature']['SignatureValid'] is True:
                passed.append(True)
                certificates.append(signature['ChainItem'])
            else:
                passed.append(False)
                certificates.append(signature['ChainItem'])
        
        return passed, certificates, 200
    except Exception as e:
        return jsonify({"status": False, "message": "Error in validation_analyze" + str(e)}), 500

def validate_certs(certs):
    """
    Validate the certificates.

    Args:
        certs (list): List of certificates.

    Returns:
        bool: True if all certificates are valid, False otherwise.
    """
    try:
        return True, 200
    except Exception as e:
        return jsonify({"status": False, "message": "Error in validate_certs" + str(e)}), 500

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

    current_time = int(tiempo.time() * 1000)

    for index_data in indexes_data:
        try:
            index = index_data['index']
            jsonb64 = copy.deepcopy(index)
            # Save the jsonb64 to a file
            try:
                with open('jsonb64_backup.txt', 'w') as f:
                    f.write(jsonb64)
            except Exception as e:
                print(f"Error saving jsonb64 to file: {str(e)}")
            # Decode and re-encode the entire JSON object to fix character encoding issues

            index = json.loads(base64.b64decode(jsonb64).decode('utf-8'))
            # Save the index to a file
            try:
                with open('index_backup.json', 'w') as f:
                    json.dump(index, f, separators=(',', ':'), ensure_ascii=False)
            except Exception as e:
                print(f"Error saving index to file: {str(e)}")

            tramites = index['tramites']

            name = data_signature['name']
            stamp = data_signature['stamp']
            area = data_signature['area']
            isdigital = data_signature['isdigital']
            filepath = index_data['path']

            tramite = tramites[-1]

            role = name + ", " + stamp + ", " + area

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
                message, code = save_signed_json(index, "./json3.json")
                if code != 200:
                    errors_stack.append({"idExpFailed": f"{index['numero']}/{index['anio']}/{index['codigo']}/{index['letra']}", "message": "Error al guardar PDF firmado" + str(message)})
                    raise PDFSignatureError("Error al guardar index firmado")
                id_exps_signeds.append(f"{index['numero']}/{index['anio']}/{index['codigo']}/{index['letra']}")
        
        except PDFSignatureError as e:
            print(e)
        
    exps_not_signed = []
    for error in errors_stack:
        exps_not_signed.append(error['idExpFailed'])

    return jsonify({"status": True, "expsSigned": id_exps_signeds, "expsNotSigned": exps_not_signed, "dataToSign": data_to_sign}), 200

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
    
    for index_data in indexes_data:
        try:
            index = index_data['index']
            jsonb64 = copy.deepcopy(index)
            # Save the jsonb64 to a file
            try:
                with open('jsonb64_backup.txt', 'w') as f:
                    f.write(jsonb64)
            except Exception as e:
                print(f"Error saving jsonb64 to file: {str(e)}")
            # Decode and re-encode the entire JSON object to fix character encoding issues

            index = json.loads(base64.b64decode(jsonb64).decode('utf-8'))
            # Save the index to a file
            try:
                with open('index_backup.json', 'w') as f:
                    json.dump(index, f, separators=(',', ':'), ensure_ascii=False)
            except Exception as e:
                print(f"Error saving index to file: {str(e)}")

            tramites = index['tramites']

            name = data_signature['name']
            stamp = data_signature['stamp']
            area = data_signature['area']
            isdigital = data_signature['isdigital']
            filepath = index_data['path']

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

            message, code = save_signed_json(index, "./json4.json")
            if code != 200:
                errors_stack.append({"idExpFailed": f"{index['numero']}/{index['anio']}/{index['codigo']}/{index['letra']}", "message": "Error al guardar PDF firmado" + str(message)})
                raise PDFSignatureError("Error al guardar indice firmado")
            id_exps_signeds.append(f"{index['numero']}/{index['anio']}/{index['codigo']}/{index['letra']}")

        except PDFSignatureError as e:
            print(e)
    
    exps_not_signed = []
    for error in errors_stack:
        exps_not_signed.append(error['idExpFailed'])

    return jsonify({"status": True, "expsSigned": id_exps_signeds, "expsNotSigned": exps_not_signed}), 200  

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
    
def save_signed_json(index, filepath):
    try:
        with open(filepath, 'w') as file:
            json.dump(index, file, separators=(',', ':'), ensure_ascii=False)
        return True, 200
    except Exception as e:
        return jsonify({"status": False, "message": "Error al guardar el indice firmado: " + str(e)}), 500
        
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

            passed, certs, code = validation_analyze(valid)
            if code != 200:
                raise PDFSignatureError("Error en validation_analyze")

            for test in passed:
                # Store the validation result
                tested = bool(test)
                if not tested:
                    break

            certs_validation, code = validate_certs(certs)
            if code != 200:
                raise PDFSignatureError("Error en validate_certs")

            indication = True if certs_validation and tested else False

            validation_results.append({
                'secuencia': tramite['secuencia'],
                'is_valid': tested,
                'certs_valid': certs_validation,
                'subindication': indication
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
