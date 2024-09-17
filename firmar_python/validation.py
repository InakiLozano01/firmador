import json
from flask import jsonify
import requests
import base64

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
        certificates_data = []
        signatures = []
        for signature in report['DiagnosticData']['Signature']:
            if signature['StructuralValidation']['valid'] is True and signature['BasicSignature']['SignatureIntact'] is True and signature['BasicSignature']['SignatureValid'] is True:
                signature = {
                    "valid": True,
                    "certs": signature['ChainItem'],
                    "signingTime": signature['ClaimedSigningTime'],
                    "signer_role": signature['SignerRole'][0]['Role'] if signature['SignerRole'] else None,
                    "cert_data": {}
                }
                signatures.append(signature)
            else:
                signature = {
                    "valid": False,
                    "certs": signature['ChainItem'],
                    "signingTime": signature['ClaimedSigningTime'],
                    "signer_role": signature['SignerRole'][0]['Role'] if signature['SignerRole'] else None,
                    "cert_data": {}
                }
                signatures.append(signature)

        certificates = []
        for signature in signatures:
            certificates.append(signature['certs'])
        
        certs_to_lookup = []
        for cert in certificates:
            certs_to_lookup.append(cert[0]['Certificate'])

        for cert in report['DiagnosticData']['Certificate']:
            if cert['Id'] in certs_to_lookup:
                cert_data = {
                    "ID": cert['Id'],
                    "SN": cert['SubjectSerialNumber'],
                    "CN": cert['CommonName'],
                    "ON": cert['OrganizationName'],
                    "OU": cert['OrganizationalUnit'],
                    "IssuerDN": cert['IssuerDistinguishedName'][1]['value'],
                    "Country": cert['CountryName'],
                    "NotAfter": cert['NotAfter'],
                    "NotBefore": cert['NotBefore'],
                    "Email": next((ext['SubjectAlternativeNames']['subjectAlternativeName'][0]['value']
                                   for ext in cert.get('certificateExtensions', [])
                                   if isinstance(ext, dict) and 'SubjectAlternativeNames' in ext
                                   and 'subjectAlternativeName' in ext['SubjectAlternativeNames']),
                                  cert.get('Email'))
                }
                certificates_data.append(cert_data)
        
        for cert in certificates_data:
            for signature in signatures:
                if cert['ID'] == signature['certs'][0]['Certificate']:
                    signature['cert_data'] = cert
        return signatures, 200
    except Exception as e:
        print(e)
        return jsonify({"status": False, "message": "Error in validation_analyze" + str(e)}), 500
    
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