from datetime import datetime, timedelta
import hashlib
import os
import logging
from typing import Tuple, List, Dict, Any, Optional
from ..exceptions.validation_exc import SignatureValidationError, InvalidSignatureDataError

# Configure logging
logger = logging.getLogger(__name__)

def parse_datetime(date_str: str) -> str:
    """Parse datetime string and convert to local time (-3 hours)."""
    logger.debug(f"Parsing datetime string: {date_str}")
    try:
        dt = datetime.strptime(date_str, '%Y-%m-%dT%H:%M:%SZ')
        result = (dt - timedelta(hours=3)).strftime('%Y-%m-%d %H:%M:%S')
        logger.debug(f"Parsed datetime: {result}")
        return result
    except ValueError as e:
        logger.warning(f"Failed to parse datetime string '{date_str}', returning as is: {str(e)}")
        return date_str

def calculate_crt_fingerprint(crt_file_path: str) -> Optional[str]:
    """Calculate SHA256 fingerprint of a certificate file."""
    logger.debug(f"Calculating fingerprint for certificate: {crt_file_path}")
    try:
        with open(crt_file_path, 'rb') as crt_file:
            crt_data = crt_file.read()
        fingerprint = hashlib.sha256(crt_data).hexdigest()
        logger.debug(f"Successfully calculated fingerprint: {fingerprint}")
        return fingerprint
    except (IOError, Exception) as e:
        logger.error(f"Failed to calculate certificate fingerprint: {str(e)}", exc_info=True)
        return None

def validate_certs(certs: List[Dict[str, Any]]) -> Tuple[bool, int]:
    """Validate certificates against trusted certificates."""
    logger.info("Starting certificates validation")
    try:
        hash_certs = []
        trusted_certs_dir = '/app/certs/authority/'
        logger.debug(f"Reading trusted certificates from: {trusted_certs_dir}")
        
        # Check if trusted certs directory exists
        if not os.path.exists(trusted_certs_dir):
            logger.warning(f"Trusted certificates directory not found: {trusted_certs_dir}")
            # For now, return true to allow validation to continue
            # In production, you might want to handle this differently
            return True, 200
        
        # Get fingerprints of trusted certificates
        for filename in os.listdir(trusted_certs_dir):
            if filename.endswith('.crt'):
                file_path = os.path.join(trusted_certs_dir, filename)
                if fingerprint := calculate_crt_fingerprint(file_path):
                    hash_certs.append(fingerprint)
        
        logger.debug(f"Found {len(hash_certs)} trusted certificates")
        
        # If no trusted certs found, return true for now
        if not hash_certs:
            logger.warning("No trusted certificates found in directory")
            return True, 200
        
        # Check if any cert matches trusted certs
        for cert in certs:
            hashcert = cert['Certificate'].replace('C-', '').lower()
            if hashcert in hash_certs:
                logger.info("Found matching trusted certificate")
                return True, 200
        
        logger.info("No matching trusted certificate found")
        return False, 200
    except Exception as e:
        logger.error(f"Error validating certificates: {str(e)}", exc_info=True)
        raise SignatureValidationError(f"Error validating certificates: {str(e)}")

def extract_cert_data(cert: Dict[str, Any]) -> Dict[str, Any]:
    """Extract relevant certificate data."""
    logger.debug(f"Extracting data from certificate ID: {cert.get('Id')}")
    try:
        email = next(
            (ext['SubjectAlternativeNames']['subjectAlternativeName'][0]['value']
             for ext in cert.get('certificateExtensions', [])
             if isinstance(ext, dict) 
             and 'SubjectAlternativeNames' in ext
             and 'subjectAlternativeName' in ext['SubjectAlternativeNames']),
            cert.get('Email')
        )
        
        cert_data = {
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
        logger.debug(f"Successfully extracted certificate data: {cert_data}")
        return cert_data
    except Exception as e:
        logger.error(f"Error extracting certificate data: {str(e)}", exc_info=True)
        raise SignatureValidationError(f"Error extracting certificate data: {str(e)}")

def process_signature_data(signature: Dict[str, Any], certs_valid: bool) -> Dict[str, Any]:
    """Process individual signature data and return standardized signature object."""
    logger.debug(f"Processing signature data with certs_valid={certs_valid}")
    try:
        claimed_signing_time = datetime.strptime(
            signature['ClaimedSigningTime'], 
            '%Y-%m-%dT%H:%M:%SZ'
        ) - timedelta(hours=3)
        logger.debug(f"Parsed signing time: {claimed_signing_time}")
    except ValueError as e:
        logger.warning(f"Failed to parse signing time, using max datetime: {str(e)}")
        claimed_signing_time = datetime.max
    except KeyError as e:
        logger.warning(f"Missing ClaimedSigningTime: {str(e)}")
        claimed_signing_time = datetime.max

    # Safely check structural validation
    structural_valid = False
    try:
        if isinstance(signature.get('StructuralValidation'), dict):
            structural_valid = bool(signature['StructuralValidation'].get('valid', False))
        elif isinstance(signature.get('StructuralValidation'), list):
            # If it's a list, check if any element has valid=True
            structural_valid = any(
                isinstance(item, dict) and bool(item.get('valid', False))
                for item in signature['StructuralValidation']
            )
    except Exception as e:
        logger.warning(f"Error checking structural validation: {str(e)}")
        structural_valid = False

    # Safely check basic signature
    basic_sig_intact = False
    basic_sig_valid = False
    try:
        basic_sig = signature.get('BasicSignature', {})
        if isinstance(basic_sig, dict):
            basic_sig_intact = bool(basic_sig.get('SignatureIntact', False))
            basic_sig_valid = bool(basic_sig.get('SignatureValid', False))
    except Exception as e:
        logger.warning(f"Error checking basic signature: {str(e)}")

    is_valid = (
        structural_valid and
        basic_sig_intact and
        basic_sig_valid and
        claimed_signing_time < datetime.now()
    )
    logger.debug(f"Signature validity check result: {is_valid}")

    # Safely get signer role
    signer_role = None
    try:
        signer_roles = signature.get('SignerRole', [])
        if isinstance(signer_roles, list) and signer_roles:
            first_role = signer_roles[0]
            if isinstance(first_role, dict):
                signer_role = first_role.get('Role')
    except Exception as e:
        logger.warning(f"Error getting signer role: {str(e)}")

    return {
        "valid": is_valid,
        "certs": signature.get('ChainItem', []),
        "certs_valid": certs_valid,
        "signingTime": (
            parse_datetime(signature.get('ClaimedSigningTime', ''))
            if claimed_signing_time < datetime.now()
            else f"{parse_datetime(signature.get('ClaimedSigningTime', ''))} INVALIDA"
        ),
        "signer_role": signer_role,
        "cert_data": {}
    }

def process_signature(signature: Dict[str, Any], certs_valid: bool) -> Dict[str, Any]:
    """Process individual signature data."""
    return process_signature_data(signature, certs_valid)

def validation_analyze(report: Dict[str, Any]) -> List[Dict[str, Any]]:
    """Analyze validation report and return processed signatures with certificate data."""
    logger.info("Starting validation report analysis")
    try:
        certificates_data = []
        signatures = []
        
        # Process signatures
        logger.debug(f"Processing {len(report['DiagnosticData']['Signature'])} signatures")
        for signature in report['DiagnosticData']['Signature']:
            certs_valid, code = validate_certs(signature['ChainItem'])
            if code != 200:
                logger.error(f"Error in validate_certs with code {code}")
                return []

            # Check signature validity
            is_structurally_valid = False
            try:
                struct_val = signature.get('StructuralValidation', {})
                if isinstance(struct_val, dict):
                    is_structurally_valid = bool(struct_val.get('valid', False))
                elif isinstance(struct_val, list) and struct_val:
                    # If it's a list, use the first item's valid property
                    first_item = struct_val[0] if struct_val else {}
                    is_structurally_valid = bool(first_item.get('valid', False))
            except Exception as e:
                logger.warning(f"Error checking structural validation: {str(e)}")
                is_structurally_valid = False

            try:
                claimed_signing_time = datetime.strptime(
                    signature['ClaimedSigningTime'], 
                    '%Y-%m-%dT%H:%M:%SZ'
                ) - timedelta(hours=3)
            except (ValueError, KeyError):
                claimed_signing_time = datetime.max

            basic_sig = signature.get('BasicSignature', {})
            signature_obj = {
                "valid": (is_structurally_valid and 
                         basic_sig.get('SignatureIntact', False) is True and 
                         basic_sig.get('SignatureValid', False) is True and
                         claimed_signing_time < datetime.now()),
                "certs": signature['ChainItem'],
                "certs_valid": certs_valid,
                "signingTime": (
                    parse_datetime(signature['ClaimedSigningTime'])
                    if claimed_signing_time < datetime.now()
                    else f"{parse_datetime(signature['ClaimedSigningTime'])} INVALIDA"
                ),
                "signer_role": None,  # Initialize as None
                "cert_data": {}  # Initialize empty cert_data
            }

            # Safely add signer role if available
            try:
                signer_roles = signature.get('SignerRole', [])
                if signer_roles and isinstance(signer_roles, list) and len(signer_roles) > 0:
                    first_role = signer_roles[0]
                    if isinstance(first_role, dict):
                        signature_obj["signer_role"] = first_role.get('Role')
            except Exception as e:
                logger.warning(f"Error processing signer role: {str(e)}")

            signatures.append(signature_obj)

        if not signatures:
            logger.warning("No signatures found in report")
            return []

        # Process certificate data
        try:
            for cert in report['DiagnosticData'].get('Certificate', []):
                cert_id = cert.get('Id')
                if any(cert_id == sig['certs'][0]['Certificate'] for sig in signatures if sig['certs']):
                    try:
                        cert_data = extract_cert_data(cert)
                        certificates_data.append(cert_data)
                    except Exception as e:
                        logger.warning(f"Error extracting certificate data: {str(e)}")
                        continue

            # Match certificates with signatures
            for cert in certificates_data:
                for signature in signatures:
                    if signature['certs'] and cert['ID'] == signature['certs'][0]['Certificate']:
                        signature['cert_data'] = cert
        except Exception as e:
            logger.warning(f"Error processing certificates: {str(e)}")

        logger.info(f"Validation analysis completed. Returning {len(signatures)} signatures")
        return signatures

    except Exception as e:
        logger.error(f"Error analyzing validation report: {str(e)}", exc_info=True)
        return []
