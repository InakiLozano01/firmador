# Descripcion: Modulo que contiene las funciones para obtener el certificado y valor de firma de nexU del Host

import requests
import logging
from errors import PDFSignatureError

def get_certificate_from_nexu(host):
    try:
        response = requests.get('http://'+ host +':50000/certificados')
        response.raise_for_status()
        certificatesjson = response.json()
        return certificatesjson
    except requests.RequestException as e:
        logging.error(f"Error in get_certificate_from_nexu: {str(e)}")
        raise PDFSignatureError("Failed to obtain certificate from NexU.")
    
    
def get_signature_value(data_to_sign, certificate_data, host):
    try:
        body = {
            "tokenId": certificate_data['response']['tokenId'],
            "keyId": certificate_data['response']['keyId'],
            "toBeSigned": {"bytes": data_to_sign},
            "digestAlgorithm": "SHA256"
        }
        response = requests.post('http://' + host + ':50000/firmar', json=body)
        signjson = response.json()
        return signjson['response']['signatureValue']
    except requests.RequestException as e:
        logging.error(f"Error in get_signature_value: {str(e)}")
        raise PDFSignatureError("Failed to get signature value from NexU.")