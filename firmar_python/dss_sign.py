# Descripcion: Este modulo contiene las funciones necesarias para firmar un documento PDF con la API de DSS y certificado propio
import requests
import base64
import logging
from errors import PDFSignatureError
import io 
from PyPDF2 import PdfReader

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
                "signatureLevel": "PAdES_BASELINE_B",
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
                    "signingDate": current_time,  # Current time in milliseconds
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
        response = requests.post('http://localhost:5555/services/rest/signature/one-document/getDataToSign', json=body)
        response.raise_for_status()
        return response.json()
    except requests.RequestException as e:
        logging.error(f"Error in get_data_to_sign: {str(e)}")
        raise PDFSignatureError("Failed to get data to sign from DSS API.")

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
                "signatureLevel": "PAdES_BASELINE_B",
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
                    "signingDate": current_time,  # Current time in milliseconds
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
        response = requests.post('http://localhost:5555/services/rest/signature/one-document/signDocument', json=body)
        response.raise_for_status()
        return response.json()
    except requests.RequestException as e:
        logging.error(f"Error in sign_document: {str(e)}")
        raise PDFSignatureError("Failed to sign document with DSS API.")

'''def get_data_to_sign_own(pdf, certificates, current_time, field_id, stamp, encoded_image):
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
                "signatureLevel": "PAdES_BASELINE_B",
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
                    "dpi": 0,
                    "image": None,
                    "fieldParameters": None,
                    "textParameters": None,
                    "zoom": None
                },
                "signatureIdToCounterSign": None,
                "blevelParams": {
                    "trustAnchorBPPolicy": True,
                    "signingDate": current_time,  # Current time in milliseconds
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
        response = requests.post('http://localhost:5555/services/rest/signature/one-document/getDataToSign', json=body)
        response.raise_for_status()
        return response.json()
    except requests.RequestException as e:
        logging.error(f"Error in get_data_to_sign: {str(e)}")
        raise PDFSignatureError("Failed to get data to sign from DSS API.")
    
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
                "signatureLevel": "PAdES_BASELINE_B",
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
                    "dpi": 0,
                    "image": None,
                    "fieldParameters": None,
                    "textParameters": None,
                    "zoom": None
                },
                "signatureIdToCounterSign": None,
                "blevelParams": {
                    "trustAnchorBPPolicy": True,
                    "signingDate": current_time,  # Current time in milliseconds
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
        response = requests.post('http://localhost:5555/services/rest/signature/one-document/signDocument', json=body)
        response.raise_for_status()
        return response.json()
    except requests.RequestException as e:
        logging.error(f"Error in sign_document: {str(e)}")
        raise PDFSignatureError("Failed to sign document with DSS API.")'''

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
                "signatureLevel": "PAdES_BASELINE_B",
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
                    "signingDate": current_time,  # Current time in milliseconds
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
        response = requests.post('http://localhost:5555/services/rest/signature/one-document/getDataToSign', json=body)
        response.raise_for_status()
        return response.json()
    except requests.RequestException as e:
        logging.error(f"Error in get_data_to_sign_tapir: {str(e)}")
        raise PDFSignatureError("Failed to get data to sign from DSS API.")

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
                "signatureLevel": "PAdES_BASELINE_B",
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
                    "signingDate": current_time,  # Current time in milliseconds
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
        response = requests.post('http://localhost:5555/services/rest/signature/one-document/signDocument', json=body)
        response.raise_for_status()
        return response.json()
    except requests.RequestException as e:
        logging.error(f"Error in sign_document_tapir: {str(e)}")
        raise PDFSignatureError("Failed to sign document with DSS API.")