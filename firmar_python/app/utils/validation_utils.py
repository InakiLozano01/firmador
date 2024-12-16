from datetime import datetime, timedelta
import hashlib
import os
from typing import Tuple, List, Dict, Any, Optional
from ..exceptions.validation_exc import SignatureValidationError, InvalidSignatureDataError

def parse_datetime(date_str: str) -> str:
    """Parse datetime string and convert to local time (-3 hours)."""
    try:
        dt = datetime.strptime(date_str, '%Y-%m-%dT%H:%M:%SZ')
        return (dt - timedelta(hours=3)).strftime('%Y-%m-%d %H:%M:%S')
    except ValueError:
        return date_str

def calculate_crt_fingerprint(crt_file_path: str) -> Optional[str]:
    """Calculate SHA256 fingerprint of a certificate file."""
    try:
        with open(crt_file_path, 'rb') as crt_file:
            crt_data = crt_file.read()
        return hashlib.sha256(crt_data).hexdigest()
    except (IOError, Exception) as e:
        return None

def validate_certs(certs: List[Dict[str, Any]]) -> Tuple[bool, int]:
    """Validate certificates against trusted certificates."""
    try:
        hash_certs = []
        trusted_certs_dir = '/app/trustedcerts/'
        
        # Get fingerprints of trusted certificates
        for filename in os.listdir(trusted_certs_dir):
            if filename.endswith('.crt'):
                file_path = os.path.join(trusted_certs_dir, filename)
                if fingerprint := calculate_crt_fingerprint(file_path):
                    hash_certs.append(fingerprint)
        
        # Check if any cert matches trusted certs
        for cert in certs:
            hashcert = cert['Certificate'].replace('C-', '').lower()
            if hashcert in hash_certs:
                return True, 200
                
        return False, 200
    except Exception as e:
        raise SignatureValidationError(f"Error validating certificates: {str(e)}")

def extract_cert_data(cert: Dict[str, Any]) -> Dict[str, Any]:
    """Extract relevant certificate data."""
    email = next(
        (ext['SubjectAlternativeNames']['subjectAlternativeName'][0]['value']
         for ext in cert.get('certificateExtensions', [])
         if isinstance(ext, dict) 
         and 'SubjectAlternativeNames' in ext
         and 'subjectAlternativeName' in ext['SubjectAlternativeNames']),
        cert.get('Email')
    )
    
    return {
        "ID": cert['Id'],
        "SN": cert['SubjectSerialNumber'],
        "CN": cert['CommonName'],
        "ON": cert['OrganizationName'],
        "OU": cert['OrganizationalUnit'],
        "IssuerDN": cert['IssuerDistinguishedName'][1]['value'],
        "Country": cert['CountryName'],
        "NotAfter": parse_datetime(cert['NotAfter']),
        "NotBefore": parse_datetime(cert['NotBefore']),
        "Email": email
    }

def process_signature(signature: Dict[str, Any], certs_valid: bool) -> Dict[str, Any]:
    """Process individual signature data."""
    try:
        claimed_signing_time = datetime.strptime(
            signature['ClaimedSigningTime'], 
            '%Y-%m-%dT%H:%M:%SZ'
        ) - timedelta(hours=3)
    except ValueError:
        claimed_signing_time = datetime.max

    is_valid = (
        signature['StructuralValidation']['valid'] and
        signature['BasicSignature']['SignatureIntact'] and
        signature['BasicSignature']['SignatureValid'] and
        claimed_signing_time < datetime.now()
    )

    return {
        "valid": is_valid,
        "certs": signature['ChainItem'],
        "certs_valid": certs_valid,
        "signingTime": (
            parse_datetime(signature['ClaimedSigningTime'])
            if claimed_signing_time < datetime.now()
            else f"{parse_datetime(signature['ClaimedSigningTime'])} INVALIDA"
        ),
        "signer_role": signature['SignerRole'][0]['Role'] if signature['SignerRole'] else None,
        "cert_data": {}
    }

def validation_analyze(report: Dict[str, Any]) -> Tuple[List[Dict[str, Any]], int]:
    """Analyze validation report and return processed signatures with certificate data."""
    try:
        signatures = []
        certificates_data = []

        # Process signatures
        for sig in report['DiagnosticData']['Signature']:
            certs_valid, code = validate_certs(sig['ChainItem'])
            signature = process_signature(sig, certs_valid)
            signatures.append(signature)

        # Extract certificates to look up
        certs_to_lookup = [
            sig['certs'][0]['Certificate'] 
            for sig in signatures
        ]

        # Process certificate data
        for cert in report['DiagnosticData']['Certificate']:
            if cert['Id'] in certs_to_lookup:
                cert_data = extract_cert_data(cert)
                certificates_data.append(cert_data)

        # Match certificates with signatures
        for cert in certificates_data:
            for signature in signatures:
                if cert['ID'] == signature['certs'][0]['Certificate']:
                    signature['cert_data'] = cert

        return signatures, 200

    except KeyError as e:
        raise InvalidSignatureDataError(f"Missing required field in report: {str(e)}")
    except Exception as e:
        raise SignatureValidationError(f"Error analyzing validation report: {str(e)}")
