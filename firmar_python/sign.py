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
        return jsonify({"status": "error", "message": "Error en signown: " + str(e)}), 500

##################################################
###         Función para cerrar el PDF         ###
##################################################

def closePDF(pdfToClose, json_fieldValues):
    try:
        data = {
                    'fileBase64': pdfToClose,
                    'fileName': "documento.pdf",
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
    global conn
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
            json_fieldValues1 = {
                "numero": datos_json['numero'],
                "fecha": datos_json['fecha']
            }
            json_fieldValues = json.dumps(json_fieldValues1)
            
            if datos_json['status'] == False:
                raise Exception("Error al obtener fecha y numero: " + datos_json['message'])
            else:
                try:
                    pdf, code = closePDF(pdfToClose, json_fieldValues)
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
def unlockPDF_and_close_task(idDoc, idUser, hashDoc, isClosed, isSigned=1):
    global conn
    try:
        if conn:
            if conn.closed == 0:
                cursor = conn.cursor()
        else:
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
            except Exception as e:
                return jsonify({"status": "error", "message": "Error al conectar a la base de datos: " + str(e)}), 500
    except psycopg2.InterfaceError as e:
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
            except Exception as e:
                return jsonify({"status": "error", "message": "Error al conectar a la base de datos: " + str(e)}), 500

    try:
        cursor.execute("SELECT f_finalizar_proceso_firmado (%s, %s, %s, %s, %s)", (idDoc, idUser, isSigned, isClosed, hashDoc,))
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
    global current_time, datetimesigned, conn, encoded_image
    try:
        data = request.get_json()
        pdfs = data['pdfs']
        certificates = data['certificates']
    except Exception as e:
        return jsonify({"status": False, "message": "Error al obtener los datos de la request: " + str(e)}), 500

    array_pdfs = []
    idDocsSigneds = []
    errorsStack = []
    dataToSign = []
    
    for pdf in pdfs:
        try:
            pdf_b64 = pdf['pdf']

            field_id = pdf['firma_lugar']
            name = pdf['firma_nombre']
            stamp = pdf['firma_sello']
            area = pdf['firma_area']

            isclosing = pdf['firma_cierra']        
            closingplace = pdf['firma_lugarcierre']
            idDoc = pdf['id_doc']
            isdigital = pdf['firma_digital']

            idUSer = pdf['id_usuario']
            filepath = pdf['path_file']

            current_time = int(tiempo.time() * 1000)
            datetimesigned = datetime.now(pytz.utc).astimezone(pytz.timezone('America/Argentina/Buenos_Aires')).strftime("%Y-%m-%d %H:%M:%S")

            if isdigital:
                name, code = extract_certificate_info_name(certificates['certificate'])
                if code != 200:
                    errorsStack.append({"idDocFailed": idDoc, "message": "Error al extraer nombre del certificado"})
                    raise PDFSignatureError("Error al extraer nombre del certificado")

            if isdigital:
                custom_image, code = create_signature_image(
                                f"{name}\n{datetimesigned}\n{stamp}\n{area}",
                                encoded_image,
                                "token"
                            )
                if code != 200:
                    errorsStack.append({"idDocFailed": idDoc, "message": "Error al crear imagen de firma"})
                    raise PDFSignatureError("Error al crear imagen de firma")
                
            match (isdigital, isclosing):
                case (True, True):
                    data_to_sign_response, code = get_data_to_sign_tapir(pdf_b64, certificates, current_time, field_id, stamp, custom_image)
                    if code == 500:
                        errorsStack.append({"idDocFailed": idDoc, "message": "Error al obtener datos para firmar: Error en get_data_to_sign_tapir"})
                        raise PDFSignatureError("Error al obtener datos para firmar: Error en get_data_to_sign_tapir")
                    data_to_sign = data_to_sign_response["bytes"]
                    dataToSign.append(data_to_sign)
                
                case (True, False):
                    data_to_sign_response = get_data_to_sign_tapir(pdf_b64, certificates, current_time, field_id, stamp, custom_image)
                    if code == 500:
                        errorsStack.append({"idDocFailed": idDoc, "message": "Error al obtener datos para firmar: Error en get_data_to_sign_tapir"})
                        raise PDFSignatureError("Error al obtener datos para firmar: Error en get_data_to_sign_tapir")
                    data_to_sign = data_to_sign_response["bytes"]
                    dataToSign.append(data_to_sign)

                case (False, True):
                    signed_pdf_base64, code = signown(pdf_b64, False, field_id, stamp, area, name, datetimesigned)
                    if code != 200:
                        errorsStack.append({"idDocFailed": idDoc, "message": "Error al firmar PDF: Error en signown"})
                        raise PDFSignatureError("Error al firmar PDF: Error en signown")
                    lastpdf, code = get_number_and_date_then_close(signed_pdf_base64, idDoc)
                    if code == 500:
                        response = lastpdf.get_json()
                        if response['status'] == "error":
                            errorsStack.append({"idDocFailed": idDoc, "message": "Error al cerrar PDF: Error en get_number_and_date_then_close"})
                            raise PDFSignatureError("Error al cerrar PDF: Error en get_number_and_date_then_close")
                    signed_pdf_base64_closed, code = signown(lastpdf, True, closingplace, stamp, area, name, datetimesigned)
                    if code != 200:
                        errorsStack.append({"idDocFailed": idDoc, "message": "Error al firmar PDF: Error en signown"})
                        raise PDFSignatureError("Error al firmar PDF: Error en signown")
                    finalpdf = signed_pdf_base64_closed
                    isClosed = True
                    array_pdfs.append(signed_pdf_base64_closed)
                
                case (False, False):
                    signed_pdf_base64, code = signown(pdf_b64, False, field_id, stamp, area, name, datetimesigned)
                    if code != 200:
                        errorsStack.append({"idDocFailed": idDoc, "message": "Error al firmar PDF: Error en signown"})
                        raise PDFSignatureError("Error al firmar PDF: Error en signown")
                    finalpdf = signed_pdf_base64
                    isClosed = False
                    array_pdfs.append(signed_pdf_base64)
            
            if not isdigital:
                hash_object = hashlib.sha256(io.BytesIO(base64.b64decode(finalpdf)).getvalue())
                hashDoc = hash_object.hexdigest()

                message, code = unlockPDF_and_close_task(idDoc, idUSer, hashDoc, isClosed)
                if code != 200:
                    errorsStack.append({"idDocFailed": idDoc, "message": "Error en unlockPDF_and_close_task"})
                    raise PDFSignatureError("Error en unlockPDF_and_close_task")

                message, code = save_signed_pdf(finalpdf, filepath)
                if code != 200:
                    errorsStack.append({"idDocFailed": idDoc, "message": "Error al guardar PDF firmado"})
                    raise PDFSignatureError("Error al guardar PDF firmado")
                else:
                    idDocsSigneds.append(idDoc)
            
        except PDFSignatureError as e:
            if conn:
                if conn.closed == 0:
                    conn.rollback()
                    conn.close()
        if conn:
            if conn.closed == 0:
                conn.commit()
                conn.close()

    docsNotSigned = []
    for error in errorsStack:
        docsNotSigned.append(error['idDocFailed'])

    return jsonify({"status": True, "docsSigned": idDocsSigneds, "docsNotSigned": docsNotSigned, "dataToSign": dataToSign}), 200

#2  ##################################################
    ###     Ruta de completado del proceso de      ###
    ###               firma digital                ###
    ##################################################
@app.route('/firmaloteend', methods=['POST'])
def firmaloteend():
    global current_time, datetimesigned, conn, encoded_image
    try:
        data = request.get_json()
        pdfs = data['pdfs']
        certificates = data['certificates']
    except Exception as e:
        return jsonify({"status": False, "message": "Error al obtener los datos de la request: " + str(e)}), 500
    
    array_pdfs = []
    idDocsSigneds = []
    errorsStack = []

    for pdf in pdfs:
        try:
            pdf_b64 = pdf['pdf']

            field_id = pdf['firma_lugar']
            name = pdf['firma_nombre']
            stamp = pdf['firma_sello']
            area = pdf['firma_area']

            isclosing = pdf['firma_cierra']
            closingplace = pdf['firma_lugarcierre']
            idDoc = pdf['id_doc']
            isdigital = pdf['firma_digital']

            signatureValue = pdf['signatureValue']
            idUSer = pdf['id_usuario']
            filepath = pdf['path_file']

            if isdigital:
                name, code = extract_certificate_info_name(certificates['certificate'])
                if code != 200:
                    errorsStack.append({"idDocFailed": idDoc, "message": "Error al extraer nombre del certificado"})
                    raise PDFSignatureError("Error al extraer nombre del certificado")
                
            if isdigital:
                custom_image, code = create_signature_image(
                                f"{name}\n{datetimesigned}\n{stamp}\n{area}",
                                encoded_image,
                                "token"
                            )
                if code != 200:
                    errorsStack.append({"idDocFailed": idDoc, "message": "Error al crear imagen de firma"})
                    raise PDFSignatureError("Error al crear imagen de firma")
            
            match (isdigital, isclosing):
                case (True, True):
                    signed_pdf_response, code = sign_document_tapir(pdf_b64, signatureValue, certificates, current_time, field_id, stamp, custom_image)
                    if code == 500:
                        errorsStack.append({"idDocFailed": idDoc, "message": "Error al firmar PDF: Error en sign_document_tapir"})
                        raise PDFSignatureError("Error al firmar PDF: Error en sign_document_tapir")
                    signed_pdf_base64 = signed_pdf_response['bytes']
                    lastpdf, code = get_number_and_date_then_close(signed_pdf_base64, idDoc)
                    if code == 500:
                        response = lastpdf.get_json()
                        if response['status'] == "error":
                            errorsStack.append({"idDocFailed": idDoc, "message": "Error al cerrar PDF: Error en get_number_and_date_then_close"})
                            raise PDFSignatureError("Error al cerrar PDF: Error en get_number_and_date_then_close")
                    lastsignedpdf, code = signown(lastpdf, True, closingplace, stamp, area, name, datetimesigned)
                    if code != 200:
                        errorsStack.append({"idDocFailed": idDoc, "message": "Error al firmar PDF: Error en signown"})
                        raise PDFSignatureError("Error al firmar PDF: Error en signown")
                    finalpdf = lastsignedpdf
                    isClosed = True
                    array_pdfs.append(lastsignedpdf)

                case (True, False):
                    signed_pdf_response, code = sign_document_tapir(pdf_b64, signatureValue, certificates, current_time, field_id, stamp, custom_image)
                    if code == 500:
                        errorsStack.append({"idDocFailed": idDoc, "message": "Error al firmar PDF: Error en sign_document_tapir"})
                        raise PDFSignatureError("Error al firmar PDF: Error en sign_document_tapir")
                    signed_pdf_base64 = signed_pdf_response['bytes']
                    finalpdf = signed_pdf_base64
                    isClosed = False
                    array_pdfs.append(signed_pdf_base64)
            
            hash_object = hashlib.sha256(io.BytesIO(base64.b64decode(finalpdf)).getvalue())
            hashDoc = hash_object.hexdigest()

            message, code = unlockPDF_and_close_task(idDoc, idUSer, hashDoc, isClosed)
            if code != 200:
                errorsStack.append({"idDocFailed": idDoc, "message": "Error en unlockPDF_and_close_task"})
                raise PDFSignatureError("Error en unlockPDF_and_close_task")

            message, code = save_signed_pdf(finalpdf, filepath)
            if code != 200:
                errorsStack.append({"idDocFailed": idDoc, "message": "Error al guardar PDF firmado"})
                raise PDFSignatureError("Error al guardar PDF firmado")
            else:
                idDocsSigneds.append(idDoc)
            
        except PDFSignatureError as e:
            if conn:
                if conn.closed == 0:
                    conn.rollback()
                    conn.close()
        if conn:
            if conn.closed == 0:
                conn.commit()
                conn.close()

    docsNotSigned = []
    for error in errorsStack:
        docsNotSigned.append(error['idDocFailed'])

    return jsonify({"status": True, "docsSigned": idDocsSigneds, "docsNotSigned": docsNotSigned}), 200
