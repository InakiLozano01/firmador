##################################################
###              Imports externos              ###
##################################################

import base64
import io
import requests
from PyPDF2 import PdfReader
from flask import jsonify

def digestpdf(pdf, certificate, certchain, stamp, field_id, encoded_image, current_time):
    try:
        body = {
                "parameters": {
                    "signingCertificate": {
                        "encodedCertificate": certificate
                    },
                    "certificateChain": [
                        {"encodedCertificate": cert} for cert in certchain
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
                        "alignmentHorizontal": "NONE",
                        "alignmentVertical": "NONE",
                        "imageScaling": "ZOOM_AND_CENTER",
                        "backgroundColor": {
                            "red": 255,
                            "green": 255,
                            "blue": 255,
                            "alpha": 255
                        },
                        "dpi": 200,
                        "image": {
                            "bytes": encoded_image,
                            "name": "image.png"
                        },
                        "fieldParameters": {
                            "fieldId": f"{field_id}",
                            "originX": 0,
                            "originY": 0,
                            "width": 0,
                            "height": 0,
                            "rotation": 0,
                            "page": len(PdfReader(io.BytesIO(base64.b64decode(pdf))).pages)
                        },
                        "textParameters": None,
                        "zoom": 100
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
        print(body)
        response = requests.post('http://localhost:5555/services/rest/getDataToSign', json=body)
        print(response.json())
        return response.json()
    except Exception as e:
        return jsonify({"status": "error", "message": f"Error inesperado en digestpdf: {str(e)}"}), 500
