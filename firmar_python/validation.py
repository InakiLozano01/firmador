from flask import Flask, request, jsonify, send_file
import requests
import base64
import io
from xml.etree import ElementTree as ET
from fpdf import FPDF


VALIDATION_ENDPOINT = "http://192.168.41.190:5555/services/rest/validation/validateSignature"

def parse_xml_report(xml_base64):
    xml_decoded = base64.b64decode(xml_base64).decode('utf-8')
    root = ET.fromstring(xml_decoded)
    
    report_data = []
    for sig_report in root.findall(".//ns2:SignatureValidationReport", namespaces={'ns2': 'http://uri.etsi.org/19102/v1.4.1#'}):
        signer = sig_report.find(".//ns2:Signer", namespaces={'ns2': 'http://uri.etsi.org/19102/v1.4.1#'}).text
        signing_time = sig_report.find(".//ns2:SigningTime/ns2:Time", namespaces={'ns2': 'http://uri.etsi.org/19102/v1.4.1#'}).text
        main_indication = sig_report.find(".//ns2:MainIndication", namespaces={'ns2': 'http://uri.etsi.org/19102/v1.4.1#'}).text
        sub_indication = sig_report.find(".//ns2:SubIndication", namespaces={'ns2': 'http://uri.etsi.org/19102/v1.4.1#'}).text if sig_report.find(".//ns2:SubIndication", namespaces={'ns2': 'http://uri.etsi.org/19102/v1.4.1#'}) is not None else None
        
        warnings = []
        for warning in sig_report.findall(".//ns2:ReportData[ns2:Type='urn:cef:dss:message:warning']/ns2:Value", namespaces={'ns2': 'http://uri.etsi.org/19102/v1.4.1#'}):
            warnings.append(warning.text)
        
        errors = []
        for error in sig_report.findall(".//ns2:ReportData[ns2:Type='urn:cef:dss:message:error']/ns2:Value", namespaces={'ns2': 'http://uri.etsi.org/19102/v1.4.1#'}):
            errors.append(error.text)

        report_data.append({
            "Signer": signer,
            "SigningTime": signing_time,
            "MainIndication": main_indication,
            "SubIndication": sub_indication,
            "Warnings": warnings,
            "Errors": errors
        })
    
    return report_data

def generate_pdf_report(validation_results):
    pdf = FPDF()
    pdf.add_page()
    pdf.set_font("Arial", size=12)
    
    for i, result in enumerate(validation_results, 1):
        pdf.cell(200, 10, txt=f"PDF {i}:", ln=True)
        pdf.cell(200, 10, txt=f"  Signer: {result[0]['Signer']}", ln=True)
        pdf.cell(200, 10, txt=f"  Signing Time: {result[0]['SigningTime']}", ln=True)
        pdf.cell(200, 10, txt=f"  Main Indication: {result[0]['MainIndication']}", ln=True)
        if result[0]['SubIndication']:
            pdf.cell(200, 10, txt=f"  Sub Indication: {result[0]['SubIndication']}", ln=True)
        if result[0]['Warnings']:
            pdf.cell(200, 10, txt=f"  Warnings:", ln=True)
            for warning in result[0]['Warnings']:
                pdf.cell(200, 10, txt=f"    - {warning}", ln=True)
        if result[0]['Errors']:
            pdf.cell(200, 10, txt=f"  Errors:", ln=True)
            for error in result[0]['Errors']:
                pdf.cell(200, 10, txt=f"    - {error}", ln=True)
        pdf.cell(200, 10, txt=" ", ln=True)
    
    pdf_file_path = "./report.pdf"
    pdf.output(pdf_file_path)
    
    with open(pdf_file_path, "rb") as f:
        pdf_output = io.BytesIO(f.read())
    
    return pdf_output

def validate_pdfs(pdfs_base64):
    if not pdfs_base64 or not isinstance(pdfs_base64, list):
        return jsonify({"error": "Invalid input. Expected a list of base64 PDFs."}), 400
    
    validation_results = []
    
    for pdf_base64 in pdfs_base64:
        payload = {
            "signedDocument": {
                "bytes": pdf_base64,
                "digestAlgorithm": None,
                "name": "document.pdf"
            },
            "originalDocuments": [{
                "bytes": None,
                "digestAlgorithm": None,
                "name": None
            }],
            "policy": None,
            "evidenceRecords": None,
            "tokenExtractionStrategy": "NONE",
            "signatureId": None
        }
        
        response = requests.post(VALIDATION_ENDPOINT, json=payload)
        if response.status_code == 200:
            xml_report_b64 = response.json().get("validationReportDataHandler")
            print(xml_report_b64)
            if xml_report_b64:
                validation_result = parse_xml_report(xml_report_b64)
                validation_results.append(validation_result)
            else:
                validation_results.append({"Signer": "Unknown", "Errors": ["No report available"]})
        else:
            validation_results.append({"Signer": "Unknown", "Errors": [f"Validation failed with status {response.status_code}"]})
    
    final_pdf_report = generate_pdf_report(validation_results)

validate_pdfs([base64.b64encode(open("descarga.pdf", "rb").read()).decode('utf-8')])

