import requests
import base64
import logging
import io 
from PyPDF2 import PdfReader
from flask import jsonify

def _extract_error_message(response):
    """Helper function to extract error message from DSS API response."""
    try:
        response_data = response.json()
        return response_data.get('message', response_data.get('error', 'Unknown error from DSS API'))
    except (ValueError, AttributeError):
        return response.text if hasattr(response, 'text') else 'Unknown error from DSS API'

def _handle_dss_response(response, operation_name="DSS API"):
    """Helper function to handle DSS API responses consistently."""
    if response.status_code == 200:
        response_data = response.json()
        if "bytes" in response_data:
            return response_data, 200
        else:
            # Extract error message from DSS response if available
            error_message = _extract_error_message(response)
            logging.error(f"{operation_name} error (status {response.status_code}): {error_message}")
            return jsonify({"status": False, "message": error_message}), response.status_code
    else:
        # Extract error message from DSS response if available
        error_message = _extract_error_message(response)
        logging.error(f"{operation_name} error (status {response.status_code}): {error_message}")
        return jsonify({"status": False, "message": error_message}), response.status_code

def get_data_to_sign_own(pdf, certificates, current_time, field_id, stamp, encoded_image):
    try:
        body = {
            "parameters": {
                "signingCertificate": {
                    "encodedCertificate": certificates['certificate']
                },
                "certificateChain": [
                    {"encodedCertificate": cert} for cert in certificates['certificateChain']
                ],
                "detachedContents": None,
                "asicContainerType": None,
                "signatureLevel": "PAdES_BASELINE_T",
                "signaturePackaging": "ENVELOPED",
                "embedXML": False,
                "manifestSignature": False,
                "jwsSerializationType": None,
                "sigDMechanism": None,
                "signatureAlgorithm": "RSA_SHA256",
                "digestAlgorithm": "SHA256",
                "encryptionAlgorithm": "RSA",
                "referenceDigestAlgorithm": None,
                "maskGenerationFunction": None,
                "contentTimestamps": None,
                "contentTimestampParameters": {
                    "digestAlgorithm": "SHA256",
                    "canonicalizationMethod": "http://www.w3.org/2001/10/xml-exc-c14n#",
                    "timestampContainerForm": None
                },
                "signatureTimestampParameters": {
                    "digestAlgorithm": "SHA256",
                    "canonicalizationMethod": "http://www.w3.org/2001/10/xml-exc-c14n#",
                    "timestampContainerForm": None
                },
                "archiveTimestampParameters": {
                    "digestAlgorithm": "SHA256",
                    "canonicalizationMethod": "http://www.w3.org/2001/10/xml-exc-c14n#",
                    "timestampContainerForm": None
                },
                "signWithExpiredCertificate": False,
                "generateTBSWithoutCertificate": False,
                "imageParameters": {
                    "alignmentHorizontal": None,
                    "alignmentVertical": None,
                    "imageScaling": "ZOOM_AND_CENTER",
                    "backgroundColor": None,
                    "dpi": 200,
                    "image": {
                        "bytes": encoded_image,
                        "name": "image.png"
                    },
                    "fieldParameters": {
                        "fieldId": f"{field_id}",
                        "originX": 0,
                        "originY": 0,
                        "width": None,
                        "height": None,
                        "rotation": None,
                        "page": len(PdfReader(io.BytesIO(base64.b64decode(pdf))).pages)
                    },
                    "textParameters": None,
                    "zoom": None
                },
                "signatureIdToCounterSign": None,
                "blevelParams": {
                    "trustAnchorBPPolicy": True,
                    "signingDate": current_time,
                    "claimedSignerRoles": [f"{stamp}"],
                    "policyId": None,
                    "policyQualifier": None,
                    "policyDescription": None,
                    "policyDigestAlgorithm": None,
                    "policyDigestValue": None,
                    "policySpuri": None,
                    "commitmentTypeIndications": None,
                    "signerLocationPostalAddress": [
                        "Congreso 180",
                        "4000 San Miguel de Tucumán",
                        "Tucumán",
                        "AR"
                    ],
                    "signerLocationPostalCode": "4000",
                    "signerLocationLocality": "San Miguel de Tucumán",
                    "signerLocationStateOrProvince": "Tucumán",
                    "signerLocationCountry": "AR",
                    "signerLocationStreet": "Congreso 180"
                }
            },
            "toSignDocument": {
                "bytes": pdf,
                "digestAlgorithm": None,
                "name": "document.pdf"
            }
        }
        response = requests.post('http://java-webapp:5555/services/rest/signature/one-document/getDataToSign', json=body)
        return _handle_dss_response(response, "get_data_to_sign_own")
    except requests.RequestException as e:
        logging.error(f"Error in get_data_to_sign_own: {str(e)}")
        return jsonify({"status": False, "message": f"Failed to connect to DSS API: {str(e)}"}), 500
    except Exception as e:
        logging.error(f"Unexpected error in get_data_to_sign_own: {str(e)}")
        return jsonify({"status": False, "message": f"Failed to get data to sign with DSS API: {str(e)}"}), 500

def sign_document_own(pdf, signature_value, certificates, current_time, field_id, stamp, encoded_image):
    try:
        body = {
            "parameters": {
                "signingCertificate": {
                    "encodedCertificate": certificates['certificate']
                },
                "certificateChain": [
                    {"encodedCertificate": cert} for cert in certificates['certificateChain']
                ],
                "detachedContents": None,
                "asicContainerType": None,
                "signatureLevel": "PAdES_BASELINE_T",
                "signaturePackaging": "ENVELOPED",
                "signatureAlgorithm": "RSA_SHA256",
                "digestAlgorithm": "SHA256",
                "encryptionAlgorithm": "RSA",
                "referenceDigestAlgorithm": None,
                "maskGenerationFunction": None,
                "contentTimestamps": None,
                "contentTimestampParameters": {
                    "digestAlgorithm": "SHA256",
                    "canonicalizationMethod": "http://www.w3.org/2001/10/xml-exc-c14n#",
                    "timestampContainerForm": None
                },
                "signatureTimestampParameters": {
                    "digestAlgorithm": "SHA256",
                    "canonicalizationMethod": "http://www.w3.org/2001/10/xml-exc-c14n#",
                    "timestampContainerForm": None
                },
                "archiveTimestampParameters": {
                    "digestAlgorithm": "SHA256",
                    "canonicalizationMethod": "http://www.w3.org/2001/10/xml-exc-c14n#",
                    "timestampContainerForm": None
                },
                "signWithExpiredCertificate": False,
                "generateTBSWithoutCertificate": False,
                "imageParameters": {
                    "alignmentHorizontal": None,
                    "alignmentVertical": None,
                    "imageScaling": "ZOOM_AND_CENTER",
                    "backgroundColor": None,
                    "dpi": 200,
                    "image": {
                        "bytes": encoded_image,
                        "name": "image.png"
                    },
                    "fieldParameters": {
                        "fieldId": f"{field_id}",
                        "originX": 0,
                        "originY": 0,
                        "width": None,
                        "height": None,
                        "rotation": None,
                        "page": len(PdfReader(io.BytesIO(base64.b64decode(pdf))).pages)
                    },
                    "textParameters": None,
                    "zoom": None
                },
                "signatureIdToCounterSign": None,
                "blevelParams": {
                    "trustAnchorBPPolicy": True,
                    "signingDate": current_time,
                    "claimedSignerRoles": [f"{stamp}"],
                    "policyId": None,
                    "policyQualifier": None,
                    "policyDescription": None,
                    "policyDigestAlgorithm": None,
                    "policyDigestValue": None,
                    "policySpuri": None,
                    "commitmentTypeIndications": None,
                    "signerLocationPostalAddress": [
                        "Congreso 180",
                        "4000 San Miguel de Tucumán",
                        "Tucumán",
                        "AR"
                    ],
                    "signerLocationPostalCode": "4000",
                    "signerLocationLocality": "San Miguel de Tucumán",
                    "signerLocationStateOrProvince": "Tucumán",
                    "signerLocationCountry": "AR",
                    "signerLocationStreet": "Congreso 180"
                }
            },
            "signatureValue": {
                "algorithm": "RSA_SHA256",
                "value": signature_value
            },
            "toSignDocument": {
                "bytes": pdf,
                "digestAlgorithm": None,
                "name": "document.pdf"
            }
        }
        response = requests.post('http://java-webapp:5555/services/rest/signature/one-document/signDocument', json=body)
        return _handle_dss_response(response, "sign_document_own")
    except requests.RequestException as e:
        logging.error(f"Error in sign_document_own: {str(e)}")
        return jsonify({"status": False, "message": f"Failed to connect to DSS API: {str(e)}"}), 500
    except Exception as e:
        logging.error(f"Unexpected error in sign_document_own: {str(e)}")
        return jsonify({"status": False, "message": f"Failed to sign document with DSS API: {str(e)}"}), 500

def get_data_to_sign_tapir(pdf, certificates, current_time, field_id, stamp, encoded_image):
    try:
        body = {
            "parameters": {
                "signingCertificate": {
                    "encodedCertificate": certificates['certificate']
                },
                "certificateChain": [
                    {"encodedCertificate": cert} for cert in certificates['certificateChain']
                ],
                "detachedContents": None,
                "asicContainerType": None,
                "signatureLevel": "PAdES_BASELINE_T",
                "signaturePackaging": "ENVELOPED",
                "embedXML": False,
                "manifestSignature": False,
                "jwsSerializationType": None,
                "sigDMechanism": None,
                "signatureAlgorithm": "RSA_SHA256",
                "digestAlgorithm": "SHA256",
                "encryptionAlgorithm": "RSA",
                "referenceDigestAlgorithm": None,
                "maskGenerationFunction": None,
                "contentTimestamps": None,
                "contentTimestampParameters": {
                    "digestAlgorithm": "SHA256",
                    "canonicalizationMethod": "http://www.w3.org/2001/10/xml-exc-c14n#",
                    "timestampContainerForm": None
                },
                "signatureTimestampParameters": {
                    "digestAlgorithm": "SHA256",
                    "canonicalizationMethod": "http://www.w3.org/2001/10/xml-exc-c14n#",
                    "timestampContainerForm": None
                },
                "archiveTimestampParameters": {
                    "digestAlgorithm": "SHA256",
                    "canonicalizationMethod": "http://www.w3.org/2001/10/xml-exc-c14n#",
                    "timestampContainerForm": None
                },
                "signWithExpiredCertificate": False,
                "generateTBSWithoutCertificate": False,
                "imageParameters": {
                    "alignmentHorizontal": None,
                    "alignmentVertical": None,
                    "imageScaling": "ZOOM_AND_CENTER",
                    "backgroundColor": None,
                    "dpi": 200,
                    "image": {
                        "bytes": encoded_image,
                        "name": "image.png"
                    },
                    "fieldParameters": {
                        "fieldId": f"{field_id}",
                        "originX": 0,
                        "originY": 0,
                        "width": None,
                        "height": None,
                        "rotation": None,
                        "page": len(PdfReader(io.BytesIO(base64.b64decode(pdf))).pages)
                    },
                    "textParameters": None,
                    "zoom": None
                },
                "signatureIdToCounterSign": None,
                "blevelParams": {
                    "trustAnchorBPPolicy": True,
                    "signingDate": current_time,
                    "claimedSignerRoles": [f"{stamp}"],
                    "policyId": None,
                    "policyQualifier": None,
                    "policyDescription": None,
                    "policyDigestAlgorithm": None,
                    "policyDigestValue": None,
                    "policySpuri": None,
                    "commitmentTypeIndications": None,
                    "signerLocationPostalAddress": [
                        "Congreso 180",
                        "4000 San Miguel de Tucumán",
                        "Tucumán",
                        "AR"
                    ],
                    "signerLocationPostalCode": "4000",
                    "signerLocationLocality": "San Miguel de Tucumán",
                    "signerLocationStateOrProvince": "Tucumán",
                    "signerLocationCountry": "AR",
                    "signerLocationStreet": "Congreso 180"
                }
            },
            "toSignDocument": {
                "bytes": pdf,
                "digestAlgorithm": None,
                "name": "document.pdf"
            }
        }
        response = requests.post('http://java-webapp:5555/services/rest/signature/one-document/getDataToSign', json=body)
        return _handle_dss_response(response, "get_data_to_sign_tapir")
    except requests.RequestException as e:
        logging.error(f"Error in get_data_to_sign_tapir: {str(e)}")
        return jsonify({"status": False, "message": f"Failed to connect to DSS API: {str(e)}"}), 500
    except Exception as e:
        logging.error(f"Unexpected error in get_data_to_sign_tapir: {str(e)}")
        return jsonify({"status": False, "message": f"Failed to get data to sign with DSS API: {str(e)}"}), 500

def sign_document_tapir(pdf, signature_value, certificates, current_time, field_id, stamp, encoded_image):
    try:
        body = {
            "parameters": {
                "signingCertificate": {
                    "encodedCertificate": certificates['certificate']
                },
                "certificateChain": [
                    {"encodedCertificate": cert} for cert in certificates['certificateChain']
                ],
                "detachedContents": None,
                "asicContainerType": None,
                "signatureLevel": "PAdES_BASELINE_T",
                "signaturePackaging": "ENVELOPED",
                "signatureAlgorithm": "RSA_SHA256",
                "digestAlgorithm": "SHA256",
                "encryptionAlgorithm": "RSA",
                "referenceDigestAlgorithm": None,
                "maskGenerationFunction": None,
                "contentTimestamps": None,
                "contentTimestampParameters": {
                    "digestAlgorithm": "SHA256",
                    "canonicalizationMethod": "http://www.w3.org/2001/10/xml-exc-c14n#",
                    "timestampContainerForm": None
                },
                "signatureTimestampParameters": {
                    "digestAlgorithm": "SHA256",
                    "canonicalizationMethod": "http://www.w3.org/2001/10/xml-exc-c14n#",
                    "timestampContainerForm": None
                },
                "archiveTimestampParameters": {
                    "digestAlgorithm": "SHA256",
                    "canonicalizationMethod": "http://www.w3.org/2001/10/xml-exc-c14n#",
                    "timestampContainerForm": None
                },
                "signWithExpiredCertificate": False,
                "generateTBSWithoutCertificate": False,
                "imageParameters": {
                    "alignmentHorizontal": None,
                    "alignmentVertical": None,
                    "imageScaling": "ZOOM_AND_CENTER",
                    "backgroundColor": None,
                    "dpi": 200,
                    "image": {
                        "bytes": encoded_image,
                        "name": "image.png"
                    },
                    "fieldParameters": {
                        "fieldId": f"{field_id}",
                        "originX": 0,
                        "originY": 0,
                        "width": None,
                        "height": None,
                        "rotation": None,
                        "page": len(PdfReader(io.BytesIO(base64.b64decode(pdf))).pages)
                    },
                    "textParameters": None,
                    "zoom": None
                },
                "signatureIdToCounterSign": None,
                "blevelParams": {
                    "trustAnchorBPPolicy": True,
                    "signingDate": current_time,
                    "claimedSignerRoles": [f"{stamp}"],
                    "policyId": None,
                    "policyQualifier": None,
                    "policyDescription": None,
                    "policyDigestAlgorithm": None,
                    "policyDigestValue": None,
                    "policySpuri": None,
                    "commitmentTypeIndications": None,
                    "signerLocationPostalAddress": [
                        "Congreso 180",
                        "4000 San Miguel de Tucumán",
                        "Tucumán",
                        "AR"
                    ],
                    "signerLocationPostalCode": "4000",
                    "signerLocationLocality": "San Miguel de Tucumán",
                    "signerLocationStateOrProvince": "Tucumán",
                    "signerLocationCountry": "AR",
                    "signerLocationStreet": "Congreso 180"
                }
            },
            "signatureValue": {
                "algorithm": "RSA_SHA256",
                "value": signature_value
            },
            "toSignDocument": {
                "bytes": pdf,
                "digestAlgorithm": None,
                "name": "document.pdf"
            }
        }
        response = requests.post('http://java-webapp:5555/services/rest/signature/one-document/signDocument', json=body)
        return _handle_dss_response(response, "sign_document_tapir")
    except requests.RequestException as e:
        logging.error(f"Error in sign_document_tapir: {str(e)}")
        return jsonify({"status": False, "message": f"Failed to connect to DSS API: {str(e)}"}), 500
    except Exception as e:
        logging.error(f"Unexpected error in sign_document_tapir: {str(e)}")
        return jsonify({"status": False, "message": f"Failed to sign document with DSS API: {str(e)}"}), 500

def get_data_to_sign_tapir_jades(json, certificates, current_time, stamp):
    try:
        body = {
            "parameters": {
                "signingCertificate": {
                    "encodedCertificate": certificates['certificate']
                },
                "certificateChain": [
                    {"encodedCertificate": cert} for cert in certificates['certificateChain']
                ],
                "detachedContents": None,
                "asicContainerType": None,
                "signatureLevel": "JAdES_BASELINE_B",
                "signaturePackaging": "DETACHED",
                "embedXML": False,
                "manifestSignature": False,
                "jwsSerializationType": None,
                "sigDMechanism": "OBJECT_ID_BY_URI",
                "signatureAlgorithm": None,
                "digestAlgorithm": "SHA256",
                "encryptionAlgorithm": None,
                "referenceDigestAlgorithm": None,
                "contentTimestamps": None,
                "contentTimestampParameters": {
                    "digestAlgorithm": "SHA256",
                    "canonicalizationMethod": "http://www.w3.org/2001/10/xml-exc-c14n#",
                    "timestampContainerForm": None
                },
                "signatureTimestampParameters": {
                    "digestAlgorithm": "SHA256",
                    "canonicalizationMethod": "http://www.w3.org/2001/10/xml-exc-c14n#",
                    "timestampContainerForm": None
                },
                "archiveTimestampParameters": {
                    "digestAlgorithm": "SHA256",
                    "canonicalizationMethod": "http://www.w3.org/2001/10/xml-exc-c14n#",
                    "timestampContainerForm": None
                },
                "signWithExpiredCertificate": False,
                "generateTBSWithoutCertificate": False,
                "blevelParams": {
                    "trustAnchorBPPolicy": True,
                    "signingDate": current_time,
                    "claimedSignerRoles": [f"{stamp}"],
                    "policyId": None,
                    "policyQualifier": None,
                    "policyDescription": None,
                    "policyDigestAlgorithm": None,
                    "policyDigestValue": None,
                    "policySpuri": None,
                    "commitmentTypeIndications": None,
                    "signerLocationPostalAddress": [
                        "Congreso 180",
                        "4000 San Miguel de Tucumán",
                        "Tucumán",
                        "AR"
                    ],
                    "signerLocationPostalCode": "4000",
                    "signerLocationLocality": "San Miguel de Tucumán",
                    "signerLocationStateOrProvince": "Tucumán",
                    "signerLocationCountry": "AR",
                    "signerLocationStreet": "Congreso 180"
                }
            },
            "toSignDocument": {
                "bytes": json,
                "digestAlgorithm": None,
                "name": "document.json"
            }
        }
        response = requests.post('http://java-webapp:5555/services/rest/signature/one-document/getDataToSign', json=body)
        return _handle_dss_response(response, "get_data_to_sign_tapir_jades")
    except requests.RequestException as e:
        logging.error(f"Error in get_data_to_sign_tapir_jades: {str(e)}")
        return jsonify({"status": False, "message": f"Failed to connect to DSS API: {str(e)}"}), 500
    except Exception as e:
        logging.error(f"Unexpected error in get_data_to_sign_tapir_jades: {str(e)}")
        return jsonify({"status": False, "message": f"Failed to get data to sign with DSS API: {str(e)}"}), 500

def sign_document_tapir_jades(json, signature_value, certificates, current_time, stamp):
    try:
        body = {
            "parameters": {
                "signingCertificate": {
                    "encodedCertificate": certificates['certificate']
                },
                "certificateChain": [
                    {"encodedCertificate": cert} for cert in certificates['certificateChain']
                ],
                "detachedContents": None,
                "asicContainerType": None,
                "signatureLevel": "JAdES_BASELINE_B",
                "signaturePackaging": "DETACHED",
                "embedXML": False,
                "manifestSignature": False,
                "jwsSerializationType": None,
                "sigDMechanism": "OBJECT_ID_BY_URI",
                "signatureAlgorithm": None,
                "digestAlgorithm": "SHA256",
                "encryptionAlgorithm": None,
                "referenceDigestAlgorithm": None,
                "contentTimestamps": None,
                "contentTimestampParameters": {
                    "digestAlgorithm": "SHA256",
                    "canonicalizationMethod": "http://www.w3.org/2001/10/xml-exc-c14n#",
                    "timestampContainerForm": None
                },
                "signatureTimestampParameters": {
                    "digestAlgorithm": "SHA256",
                    "canonicalizationMethod": "http://www.w3.org/2001/10/xml-exc-c14n#",
                    "timestampContainerForm": None
                },
                "archiveTimestampParameters": {
                    "digestAlgorithm": "SHA256",
                    "canonicalizationMethod": "http://www.w3.org/2001/10/xml-exc-c14n#",
                    "timestampContainerForm": None
                },
                "signWithExpiredCertificate": False,
                "generateTBSWithoutCertificate": False,
                "blevelParams": {
                    "trustAnchorBPPolicy": True,
                    "signingDate": current_time,
                    "claimedSignerRoles": [f"{stamp}"],
                    "policyId": None,
                    "policyQualifier": None,
                    "policyDescription": None,
                    "policyDigestAlgorithm": None,
                    "policyDigestValue": None,
                    "policySpuri": None,
                    "commitmentTypeIndications": None,
                    "signerLocationPostalAddress": [
                        "Congreso 180",
                        "4000 San Miguel de Tucumán",
                        "Tucumán",
                        "AR"
                    ],
                    "signerLocationPostalCode": "4000",
                    "signerLocationLocality": "San Miguel de Tucumán",
                    "signerLocationStateOrProvince": "Tucumán",
                    "signerLocationCountry": "AR",
                    "signerLocationStreet": "Congreso 180"
                }
            },
            "signatureValue": {
                "algorithm": "RSA_SHA256",
                "value": signature_value
            },
            "toSignDocument": {
                "bytes": json,
                "digestAlgorithm": None,
                "name": "document.json"
            }
        }
        response = requests.post('http://java-webapp:5555/services/rest/signature/one-document/signDocument', json=body)
        return _handle_dss_response(response, "sign_document_tapir_jades")
    except requests.RequestException as e:
        logging.error(f"Error in sign_document_tapir_jades: {str(e)}")
        return jsonify({"status": False, "message": f"Failed to connect to DSS API: {str(e)}"}), 500
    except Exception as e:
        logging.error(f"Unexpected error in sign_document_tapir_jades: {str(e)}")
        return jsonify({"status": False, "message": f"Failed to sign document with DSS API: {str(e)}"}), 500 