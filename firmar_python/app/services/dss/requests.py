import io
import base64
from PyPDF2 import PdfReader
from typing import Dict, Any, List

def build_base_parameters(
    certificates: Dict[str, Any],
    current_time: int,
    field_id: str,
    stamp: str,
    encoded_image: str,
    pdf: str
) -> Dict[str, Any]:
    """Build base parameters for DSS API requests"""
    return {
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
        "imageParameters": build_image_parameters(field_id, encoded_image, pdf),
        "signatureIdToCounterSign": None,
        "blevelParams": build_blevel_params(current_time, stamp)
    }

def build_image_parameters(field_id: str, encoded_image: str, pdf: str) -> Dict[str, Any]:
    """Build image parameters for DSS API requests"""
    return {
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
            "fieldId": field_id,
            "originX": 0,
            "originY": 0,
            "width": None,
            "height": None,
            "rotation": None,
            "page": len(PdfReader(io.BytesIO(base64.b64decode(pdf))).pages)
        },
        "textParameters": None,
        "zoom": None
    }

def build_blevel_params(current_time: int, stamp: str) -> Dict[str, Any]:
    """Build blevel parameters for DSS API requests"""
    return {
        "trustAnchorBPPolicy": True,
        "signingDate": current_time,
        "claimedSignerRoles": [stamp],
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

def build_request_body(
    pdf: str,
    certificates: Dict[str, Any],
    current_time: int,
    field_id: str,
    stamp: str,
    encoded_image: str,
    signature_value: str = None
) -> Dict[str, Any]:
    """Build complete request body for DSS API requests"""
    body = {
        "parameters": build_base_parameters(
            certificates,
            current_time,
            field_id,
            stamp,
            encoded_image,
            pdf
        ),
        "toSignDocument": {
            "bytes": pdf,
            "digestAlgorithm": None,
            "name": "document.pdf"
        }
    }
    
    if signature_value:
        body["signatureValue"] = {
            "algorithm": "RSA_SHA256",
            "value": signature_value
        }
    
    return body

def build_json_base_parameters(
    certificates: Dict[str, Any],
    current_time: int,
    stamp: str
) -> Dict[str, Any]:
    """Build base parameters for JSON DSS API requests"""
    return {
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
        "blevelParams": build_blevel_params(current_time, stamp)
    }

def build_json_request_body(
    json_data: str,
    certificates: Dict[str, Any],
    current_time: int,
    stamp: str,
    signature_value: str = None
) -> Dict[str, Any]:
    """Build complete request body for JSON DSS API requests"""
    body = {
        "parameters": build_json_base_parameters(
            certificates,
            current_time,
            stamp
        ),
        "toSignDocument": {
            "bytes": json_data,
            "digestAlgorithm": None,
            "name": "document.json"
        }
    }
    
    if signature_value:
        body["signatureValue"] = {
            "algorithm": "RSA_SHA256",
            "value": signature_value
        }
    
    return body 