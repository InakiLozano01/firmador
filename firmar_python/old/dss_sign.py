import requests
import base64
import logging
from errors import PDFSignatureError

def get_data_to_sign(pdf_bytes, certificate_data, x, y, page, name, cuil, email, current_time, datetimesigned):
    try:
        body = {
            "parameters": {
                "signingCertificate": {
                    "encodedCertificate": certificate_data['response']['certificate']
                },
                "certificateChain": [
                    {"encodedCertificate": cert} for cert in certificate_data['response']['certificateChain']
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
                    "imageScaling": None,
                    "backgroundColor": None,
                    "dpi": None,
                    "image": None,
                    "fieldParameters": {
                        "fieldId": None,
                        "originX": x,
                        "originY": y,
                        "width": 185.0,
                        "height": 50.0,
                        "rotation": None,
                        "page": page
                    },
                    "textParameters": {
                        "backgroundColor": {
                            "red": 255,
                            "green": 255,
                            "blue": 255,
                            "alpha": 255
                        },
                        "font": None,
                        "textWrapping": None,
                        "padding": None,
                        "signerTextHorizontalAlignment": "CENTER",
                        "signerTextVerticalAlignment": None,
                        "signerTextPosition": "TOP",
                        "size": 7,
                        "text": f"Signed by: {name}\nDate: {datetimesigned}\nE-mail: {email}\nCUIL: {cuil}",
                        "textColor": {
                            "red": 0,
                            "green": 0,
                            "blue": 0,
                            "alpha": 255
                        }
                    },
                    "zoom": None
                },
                "signatureIdToCounterSign": None,
                "blevelParams": {
                    "trustAnchorBPPolicy": True,
                    "signingDate": current_time,  # Current time in milliseconds
                    "claimedSignerRoles": None,
                    "policyId": None,
                    "policyQualifier": None,
                    "policyDescription": None,
                    "policyDigestAlgorithm": None,
                    "policyDigestValue": None,
                    "policySpuri": None,
                    "commitmentTypeIndications": None,
                    "signerLocationPostalAddress": [],
                    "signerLocationPostalCode": None,
                    "signerLocationLocality": None,
                    "signerLocationStateOrProvince": None,
                    "signerLocationCountry": "AR",
                    "signerLocationStreet": None
                }
            },
            "toSignDocument": {
                "bytes": base64.b64encode(pdf_bytes).decode('utf-8'),
                "digestAlgorithm": None,
                "name": "document.pdf"
            }
        }
        response = requests.post('http://java-webapp:5555/services/rest/signature/one-document/getDataToSign', json=body)
        response.raise_for_status()
        return response.json()
    except requests.RequestException as e:
        logging.error(f"Error in get_data_to_sign: {str(e)}")
        raise PDFSignatureError("Failed to get data to sign from DSS API.")

def sign_document(pdf_bytes, signature_value, certificate_data, x, y, page, name, cuil, email, current_time, datetimesigned):
    try:
        body = {
            "parameters": {
                "signingCertificate": {
                    "encodedCertificate": certificate_data['response']['certificate']
                },
                "certificateChain": [
                    {"encodedCertificate": cert} for cert in certificate_data['response']['certificateChain']
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
                    "imageScaling": None,
                    "backgroundColor": None,
                    "dpi": None,
                    "image": None,
                    "fieldParameters": {
                        "fieldId": None,
                        "originX": x,
                        "originY": y,
                        "width": 185.0,
                        "height": 50.0,
                        "rotation": None,
                        "page": page
                    },
                    "textParameters": {
                        "backgroundColor": {
                            "red": 255,
                            "green": 255,
                            "blue": 255,
                            "alpha": 255
                        },
                        "font": None,
                        "textWrapping": None,
                        "padding": None,
                        "signerTextHorizontalAlignment": "CENTER",
                        "signerTextVerticalAlignment": None,
                        "signerTextPosition": "TOP",
                        "size": 7,
                        "text": f"Signed by: {name}\nDate: {datetimesigned}\nE-mail: {email}\nCUIL: {cuil}",
                        "textColor": {
                            "red": 0,
                            "green": 0,
                            "blue": 0,
                            "alpha": 255
                        }
                    },
                    "zoom": None
                },
                "signatureIdToCounterSign": None,
                "blevelParams": {
                    "trustAnchorBPPolicy": True,
                    "signingDate": current_time,  # Current time in milliseconds
                    "claimedSignerRoles": None,
                    "policyId": None,
                    "policyQualifier": None,
                    "policyDescription": None,
                    "policyDigestAlgorithm": None,
                    "policyDigestValue": None,
                    "policySpuri": None,
                    "commitmentTypeIndications": None,
                    "signerLocationPostalAddress": [],
                    "signerLocationPostalCode": None,
                    "signerLocationLocality": None,
                    "signerLocationStateOrProvince": None,
                    "signerLocationCountry": "AR",
                    "signerLocationStreet": None
                }
            },
            "signatureValue": {
                "algorithm": "RSA_SHA256",
                "value": signature_value
            },
            "toSignDocument": {
                "bytes": base64.b64encode(pdf_bytes).decode('utf-8'),
                "digestAlgorithm": None,
                "name": "document.pdf"
            }
        }
        response = requests.post('http://java-webapp:5555/services/rest/signature/one-document/signDocument', json=body)
        response.raise_for_status()
        return response.json()
    except requests.RequestException as e:
        logging.error(f"Error in sign_document: {str(e)}")
        raise PDFSignatureError("Failed to sign document with DSS API.")

