from flask import Flask, request, jsonify, send_from_directory
import re
import base64
import time
from PyPDF2 import PdfReader
import io
import logging
from werkzeug.utils import secure_filename
from dss_sign import *
from manage_pdf import *
from localcerts import *
from nexu import *
from errors import PDFSignatureError
import os
import json

app = Flask(__name__)

logging.basicConfig(level=logging.root.level, format='%(asctime)s - %(levelname)s - %(message)s')

datetimesigned = time.strftime('%Y-%m-%d %H:%M:%S')

def save_signed_pdf(signed_pdf_base64, filename):
    try:
        signed_pdf_bytes = base64.b64decode(signed_pdf_base64)
        with open(filename, 'wb') as f:
            f.write(signed_pdf_bytes)
    except Exception as e:
        logging.error(f"Error in save_signed_pdf: {str(e)}")
        raise PDFSignatureError("Failed to save signed PDF.")
    
pdf = None
current_time = None
certificate_data = None
x = None
y = None
name = None
cuil = None
email = None
signed_pdf_filename = None

@app.route('/certificados', methods=['POST'])
def get_certificates():
    try:
        if 'file' not in request.files:
            raise PDFSignatureError("No file part in the request")
        
        pdf_file = request.files['file']
        if pdf_file.filename == '':
            raise PDFSignatureError("No selected file")

        if not pdf_file.filename.endswith('.pdf'):
            raise PDFSignatureError("File is not a PDF")
        
        request._load_form_data()
        body = json.loads(request.form['json'])

        pdfname = secure_filename(re.sub(r'\.pdf$', '', pdf_file.filename))
        global signed_pdf_filename
        signed_pdf_filename = pdfname + "_signed.pdf"
        pdf_bytes = pdf_file.read()
        
        # Step 1: Prepare PDF
        global x, y
        prepared_pdf_bytes, x, y = check_and_prepare_pdf(pdf_bytes)
        global pdf
        pdf = prepared_pdf_bytes

        global certificate_data
        certificate_data = body
        global cuil, name, email
        cuil, name, email = extract_certificate_info(certificate_data['certificate'])

        global current_time
        current_time = int(time.time() * 1000)

        # Step 4: Get data to sign from DSS API
        data_to_sign_response = get_data_to_sign_tapir(prepared_pdf_bytes, certificate_data, x, y, len(PdfReader(io.BytesIO(prepared_pdf_bytes)).pages), name, cuil, email, current_time, datetimesigned)
        data_to_sign = data_to_sign_response["bytes"]


        return jsonify({"status": "success", "data_to_sign": data_to_sign})
    except PDFSignatureError as e:
        return jsonify({"status": "error", "message": str(e)}), 500
    except Exception as e:
        logging.error(f"Unexpected error in get_certificates: {str(e)}")
        return jsonify({"status": "error", "message": "An unexpected error occurred."}), 500

@app.route('/firmas', methods=['POST'])
def sign_pdf_firmas():
    signature_value = request.get_json()['signatureValue']

    signed_pdf_response = sign_document_tapir(pdf, signature_value, certificate_data, x, y, len(PdfReader(io.BytesIO(pdf)).pages), name, cuil, email, current_time, datetimesigned)
    signed_pdf_base64 = signed_pdf_response['bytes']

    save_signed_pdf(signed_pdf_base64, signed_pdf_filename)

    file_path = os.path.join(os.getcwd(), signed_pdf_filename)
    response.headers["Content-Disposition"] = "attachment; filename={}".format(signed_pdf_filename)
    # Send the file as a response
    return send_file(file_path, as_attachment=True, attachment_filename=signed_pdf_filename)

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
    
        pdfname = secure_filename(re.sub(r'\.pdf$', '', pdf_file.filename))
        signed_pdf_filename = pdfname + "_signed.pdf"
        pdf_bytes = pdf_file.read()
        
        # Step 1: Prepare PDF
        prepared_pdf_bytes, x, y = check_and_prepare_pdf(pdf_bytes)

        # Step 2: Get certificate from local machine
        certificate_data = get_certificate_from_local()

        # Step 3: Extract certificate info (CUIL, name, email)
        name, email = extract_certificate_info_own()
        cuit = "30629869510"
        current_time = int(time.time() * 1000)

        # Step 4: Get data to sign from DSS API
        data_to_sign_response = get_data_to_sign_own(prepared_pdf_bytes, certificate_data, x, y, len(PdfReader(io.BytesIO(prepared_pdf_bytes)).pages), name, cuit, email, current_time, datetimesigned)
        data_to_sign = base64.b64decode(data_to_sign_response['bytes'])

        # Step 5: Get signature value with criptography
        signature_value = get_signature_value_own(data_to_sign)

        # Step 6: Apply signature to document
        signed_pdf_response = sign_document_own(prepared_pdf_bytes, signature_value, certificate_data, x, y, len(PdfReader(io.BytesIO(prepared_pdf_bytes)).pages), name, cuit, email, current_time, datetimesigned)
        signed_pdf_base64 = signed_pdf_response['bytes']

        save_signed_pdf(signed_pdf_base64, signed_pdf_filename)

        response = send_from_directory(os.getcwd(), signed_pdf_filename, as_attachment=True)
        response.headers["Content-Disposition"] = "attachment; filename={}".format(signed_pdf_filename)
        return response

    except PDFSignatureError as e:
        return jsonify({"status": "error", "message": str(e)}), 500
    except Exception as e:
        logging.error(f"Unexpected error in sign_own_pdf: {str(e)}")
        return jsonify({"status": "error", "message": "An unexpected error occurred."}), 500

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
        current_time = int(time.time() * 1000)


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

if __name__ == '__main__':
    app.run(host='0.0.0.0', debug=True, port=5000)