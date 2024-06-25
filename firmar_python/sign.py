from flask import Flask, request, jsonify, send_from_directory
import re
import base64
import time as tiempo
import PyPDF2
from PyPDF2 import PdfReader, PdfWriter
import io
import logging
from werkzeug.utils import secure_filename
from dss_sign import *
from dss_sign_own import *
from dss_sign_tapir import *
from manage_pdf import *
from localcerts import *
from certificates import *
from nexu import *
from errors import PDFSignatureError
import os
import json
from imagecomp import *
from datetime import *
import pytz
import pikepdf
from io import BytesIO
from pdfrw import *
import fitz
import pdfrw
from signimagepregenerated import *

###     Configuracion de aplicacion Flask     ###
app = Flask(__name__)

logging.basicConfig(level=logging.DEBUG, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

if __name__ == '__main__':
    app.run(host='0.0.0.0', debug=True, port=5000)
##################################################

###    Variables globales     ###
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
# Ruta para obtener PDF y certificados para firmar
@app.route('/certificados', methods=['POST'])
def get_certificates():
    global pdf, current_time, certificates, signed_pdf_filename, field_id, stamp, area, name, datetimesigned, custom_image
    
    try:
        if 'file' not in request.files:
            raise PDFSignatureError("No file part in the request")
        
        pdf_file = request.files['file']
        if pdf_file.filename == '':
            raise PDFSignatureError("No selected file")

        if not pdf_file.filename.endswith('.pdf'):
            raise PDFSignatureError("File is not a PDF")
        
        request._load_form_data()
        certificates = json.loads(request.form['certificados'])

        try:
            sign_info = json.loads(request.form['firma_info'])
        except json.JSONDecodeError:
            raise PDFSignatureError("Invalid JSON format for firma_info")

        field_id = sign_info.get('firma_lugar')
        stamp = sign_info.get('firma_sello')
        area = sign_info.get('firma_area')

        if not field_id or not stamp or not area:
            raise PDFSignatureError("firma_info is missing required fields")

        name = extract_certificate_info_name(certificates['certificate'])

        pdfname = secure_filename(re.sub(r'\.pdf$', '', pdf_file.filename))
        signed_pdf_filename = pdfname + "_signed.pdf"
        pdf = pdf_file.read()

        current_time = int(tiempo.time() * 1000)

        datetimesigned = datetime.now(pytz.utc).astimezone(pytz.timezone('America/Argentina/Buenos_Aires')).strftime("%Y-%m-%d %H:%M:%S")

        custom_image = create_signature_image(
          f"Firma Digital: {name}\n{datetimesigned}\n{stamp}\n{area}",
          compressedimage
        )

        data_to_sign_response = get_data_to_sign_tapir(pdf, certificates, current_time, datetimesigned, field_id, stamp, area, name, custom_image)
        data_to_sign = data_to_sign_response["bytes"]

        return jsonify({"status": "success", "data_to_sign": data_to_sign})
    except PDFSignatureError as e:
        return jsonify({"status": "error", "message": str(e)}), 500
    except Exception as e:
        logging.error(f"Unexpected error in get_certificates: {str(e)}")
        return jsonify({"status": "error", "message": "An unexpected error occurred."}), 500

# Ruta para firmar PDF con valor de firma
@app.route('/firmas', methods=['POST'])
def sign_pdf_firmas():
    try:

        signature_value = request.get_json()['signatureValue']

        signed_pdf_response = sign_document_tapir(pdf, signature_value, certificates, current_time, datetimesigned, field_id, stamp, area, name, custom_image)
        
        signed_pdf_base64 = signed_pdf_response['bytes']
        
        save_signed_pdf(signed_pdf_base64, signed_pdf_filename)
        
        response = send_from_directory(os.getcwd(), signed_pdf_filename, as_attachment=True)
        response.headers["Content-Disposition"] = "attachment; filename={}".format(signed_pdf_filename)
        return response
    except Exception as e:
        logging.error(f"Unexpected error in sign_pdf_firmas: {str(e)}")
        return jsonify({"status": "error", "message": "An unexpected error occurred."}), 500
###################################################


###    Ruta de la aplicacion para firmar con certificado de sistema     ###
@app.route('/signown', methods=['POST'])
def sign_own_pdf():
    try:
        if 'file' not in request.files:
            raise PDFSignatureError("No file part in the request")
        
        pdf_file = request.files['file']
        if pdf_file.filename == '':
            raise PDFSignatureError("No selected file")

        if not pdf_file.filename.endswith('.pdf'):
            raise PDFSignatureError("File is not a PDF")
    
        request._load_form_data()
        pdfname = secure_filename(re.sub(r'\.pdf$', '', pdf_file.filename))
        signed_pdf_filename = pdfname + "_signed.pdf"
        pdf = pdf_file.read()

        try:
            sign_info = json.loads(request.form['firma_info'])
        except json.JSONDecodeError:
            raise PDFSignatureError("Invalid JSON format for firma_info")

        field_id = sign_info.get('firma_lugar')
        stamp = sign_info.get('firma_sello')
        area = sign_info.get('firma_area')
        name = sign_info.get('firma_nombre')

        if not field_id or not name:
            raise PDFSignatureError("firma_info is missing required fields")
        
        
        certificates = get_certificate_from_local()

        current_time = int(tiempo.time() * 1000)

        datetimesigned = datetime.now(pytz.utc).astimezone(pytz.timezone('America/Argentina/Buenos_Aires')).strftime("%Y-%m-%d %H:%M:%S")

        data_to_sign_response = get_data_to_sign_own(pdf, certificates, current_time, datetimesigned, field_id, stamp, area, name, compressedimage)
        data_to_sign = base64.b64decode(data_to_sign_response['bytes'])

        signature_value = get_signature_value_own(data_to_sign)

        signed_pdf_response = sign_document_own(pdf, signature_value, certificates, current_time, datetimesigned, field_id, stamp, area, name, compressedimage)
        signed_pdf_base64 = signed_pdf_response['bytes']

        field_values = json.loads(request.form['pdf_form'])
        if field_values:
            data = {
                'fileBase64': signed_pdf_base64,
                'fileName': signed_pdf_filename,
                'fieldValues': json.dumps(field_values)
            }
            response = requests.post('http://java-webapp:5555/pdf/update', data=data)
            response.raise_for_status()
            signed_pdf_base64 = base64.b64encode(response.content).decode('utf-8')
        save_signed_pdf(signed_pdf_base64, signed_pdf_filename)

        response = send_from_directory(os.getcwd(), signed_pdf_filename, as_attachment=True)
        response.headers["Content-Disposition"] = "attachment; filename={}".format(signed_pdf_filename)
        return response

    except PDFSignatureError as e:
        return jsonify({"status": "error", "message": str(e)}), 500
    except Exception as e:
        logging.error(f"Unexpected error in sign_own_pdf: {str(e)}")
        return jsonify({"status": "error", "message": "An unexpected error occurred."}), 500
###################################################

###    Ruta de la aplicacion para firmar con certificado de NexU (comunicandose con host) y calculando posicion de firma    ###
@app.route('/sign', methods=['POST'])
def sign_pdf():
    host = request.headers.get('X-Real-IP')
    try:
        if 'file' not in request.files:
            raise PDFSignatureError("No file part in the request")
        
        pdf_file = request.files['file']
        if pdf_file.filename == '':
            raise PDFSignatureError("No selected file")

        if not pdf_file.filename.endswith('.pdf'):
            raise PDFSignatureError("File is not a PDF")

        pdfname = secure_filename(re.sub(r'\.pdf$', '', pdf_file.filename))
        signed_pdf_filename = pdfname + "_signed.pdf"
        pdf_bytes = pdf_file.read()

        # Step 1: Prepare PDF
        prepared_pdf_bytes, x, y = check_and_prepare_pdf(pdf_bytes)

        # Step 2: Get certificate from NexU
        certificate_data = get_certificate_from_nexu(host)

        # Step 3: Extract certificate info (CUIL, name, email)
        cert_base64 = certificate_data['response']['certificate']
        cuil, name, email = extract_certificate_info(cert_base64)
        current_time = int(tiempo.time() * 1000)

        datetimesigned = datetime.now(pytz.utc).astimezone(pytz.timezone('America/Argentina/Buenos_Aires')).strftime("%Y-%m-%d %H:%M:%S")

        # Step 4: Get data to sign from DSS API
        data_to_sign_response = get_data_to_sign(prepared_pdf_bytes, certificate_data, x, y, len(PdfReader(io.BytesIO(prepared_pdf_bytes)).pages), name, cuil, email, current_time, datetimesigned)
        data_to_sign = data_to_sign_response['bytes']
        
        # Step 5: Get signature value from NexU
        signature_value = get_signature_value(data_to_sign, certificate_data, host)

        # Step 6: Apply signature to document
        signed_pdf_response = sign_document(prepared_pdf_bytes, signature_value, certificate_data, x, y, len(PdfReader(io.BytesIO(prepared_pdf_bytes)).pages), name, cuil, email, current_time, datetimesigned)
        signed_pdf_base64 = signed_pdf_response['bytes']


        save_signed_pdf(signed_pdf_base64, signed_pdf_filename)

        response = send_from_directory(os.getcwd(), signed_pdf_filename, as_attachment=True)
        response.headers["Content-Disposition"] = "attachment; filename={}".format(signed_pdf_filename)
        return response


    except PDFSignatureError as e:
        return jsonify({"status": "error", "message": str(e)}), 500
    except Exception as e:
        logging.error(f"Unexpected error in sign_pdf: {str(e)}")
        return jsonify({"status": "error", "message": "An unexpected error occurred."}), 500
###################################################