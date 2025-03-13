import logging
from app.utils.validation_utils import process_signature, validation_analyze
from .dss.dss_valid import validate_signature_pdf, validate_signature_json
import copy
from app.exceptions import validation_exc
import libarchive
import os
import json
import re
import unicodedata
from concurrent.futures import ThreadPoolExecutor
import base64
import hashlib
import multiprocessing
from flask import jsonify
import chardet

# Configure logging
logger = logging.getLogger(__name__)

class ValidationsService:
    def __init__(self):
        cpu_count = multiprocessing.cpu_count()
        self.max_workers = cpu_count * 2/3  # Adjust based on testing
        logger.debug(f"ValidationsService initialized with {self.max_workers} workers")

    def validate_signatures_pdf(self, pdf):
        logger.info("Starting PDF signatures validation")
        pdf_b64 = pdf['pdf']
        id_doc = pdf['id_documento']
        logger.debug(f"Processing PDF with ID: {id_doc}")

        try:
            logger.debug("Validating PDF signature")
            report = validate_signature_pdf(pdf_b64)
            logger.debug("PDF signature validation completed")
        except Exception as e:
            logger.error(f"Failed to validate PDF signature for document {id_doc}: {str(e)}", exc_info=True)
            raise validation_exc.InvalidSignatureDataError(f"Error al validar PDF: Error en validate_pdf: id_doc: {id_doc}")

        try:
            logger.debug("Analyzing validation report")
            result = validation_analyze(report)
            if isinstance(result, tuple):
                signatures, _ = result
            else:
                signatures = result
            if not signatures:
                raise validation_exc.InvalidSignatureDataError(f"Error al validar PDF: No se encontraron firmas válidas: id_doc: {id_doc}")
            logger.debug("Validation analysis completed")
        except Exception as e:
            logger.error(f"Failed to analyze validation report for document {id_doc}: {str(e)}", exc_info=True)
            raise validation_exc.InvalidSignatureDataError(f"Error al validar PDF: Error en validation_analyze: id_doc: {id_doc}")

        logger.info(f"PDF signatures validation completed for document {id_doc}")
        return signatures
    
    def validate_signatures_jades(self, data):
        """
        Validate JADES signatures with comprehensive error handling.
        
        Args:
            data: The data containing tramites to validate
            
        Returns:
            tuple: (validation_result, data_original, success, message, errors_stack)
        """
        logger.info("Starting JADES signatures validation")
        validation_results = []
        errors_stack = []
        data_original = copy.deepcopy(data)
        data = copy.deepcopy(data)
        
        try:
            # Process tramites in reverse order
            for i, tramite in enumerate(reversed(data['tramites'])):
                try:
                    # Extract and validate signature
                    signature = tramite.pop('firma', '')
                    if not signature:
                        error = {
                            "secuencia": tramite.get('secuencia', i),
                            "message": "Error al obtener la firma del trámite. Posiblemente el trámite no se haya firmado"
                        }
                        errors_stack.append(error)
                        continue

                    # Validate signature
                    validation_report, status_code = validate_signature_json(data, signature)
                    if status_code != 200 or not validation_report:
                        error = {
                            "secuencia": tramite.get('secuencia', i),
                            "message": "Error en la validación de firma",
                            "status_code": status_code
                        }
                        errors_stack.append(error)
                        continue

                    # Analyze validation results
                    result_val = validation_analyze(validation_report)
                    if isinstance(result_val, tuple):
                        validation_result, _ = result_val
                    else:
                        validation_result = result_val
                    # Process validation result
                    first_signature = validation_result[0] if validation_result else None
                    tested = bool(first_signature.get('valid', False)) if first_signature else False
                    certs_valid = first_signature.get('certs_valid', False) if first_signature else False
                    indication = tested and certs_valid

                    validation_results.append({
                        'secuencia': tramite['secuencia'],
                        'is_valid': tested,
                        'certs_valid': certs_valid,
                        'subindication': indication,
                        'signature': validation_result
                    })

                    # Remove processed tramite
                    data['tramites'].remove(tramite)

                except Exception as e:
                    error = {
                        "secuencia": tramite.get('secuencia', i),
                        "message": f"Error procesando trámite: {str(e)}",
                        "stack": str(e.__traceback__)
                    }
                    errors_stack.append(error)
                    continue

            # Return early if there were errors
            if errors_stack:
                return None, data_original, False, "Error al procesar las firmas de los trámites", errors_stack

            # Prepare final validation result
            validation_results.reverse()
            validation = {
                'subresults': validation_results,
                'conclusion': all(result['subindication'] for result in validation_results)
            }

            return validation, data_original, True, "Validación completada correctamente", errors_stack

        except Exception as e:
            error = {
                "message": f"Error inesperado en la validación JADES: {str(e)}",
                "stack": str(e.__traceback__)
            }
            errors_stack.append(error)
            return None, data_original, False, "Error inesperado en la validación", errors_stack
    
    def validate_expediente(self, path):
        try:
            files = {}
            doc_order_to_filename = {}
            pdf_count = 0
            
            logger.info(f"Processing expediente at path: {path}")
            
            # Extract and process files from ZIP
            with libarchive.file_reader(path) as archive:
                for entry in archive:
                    if entry.isdir:
                        continue
                        
                    entry_pathname = entry.pathname
                    if isinstance(entry_pathname, bytes):
                        # Log raw bytes for debugging
                        logger.debug(f"Raw filename bytes: {entry_pathname!r}")
                        
                        # Use chardet for detection first
                        detected = chardet.detect(entry_pathname)
                        detected_encoding = detected['encoding']
                        confidence = detected['confidence']
                        logger.debug(f"Detected encoding: {detected_encoding} with confidence: {confidence:.2f}")
                        
                        # Initialize decoded as None
                        decoded = None
                        
                        # If high confidence detection, try that first
                        if confidence > 0.7 and detected_encoding:
                            try:
                                decoded = entry_pathname.decode(detected_encoding)
                                logger.debug(f"Successfully decoded with detected encoding {detected_encoding}: {decoded}")
                            except UnicodeDecodeError:
                                logger.debug(f"Failed to decode with detected encoding {detected_encoding} despite high confidence")
                        
                        # Try common encodings in a specific order if we haven't decoded yet
                        if decoded is None:
                            encodings_to_try = ['cp1252', 'utf-8', 'latin-1', 'iso-8859-1']
                            for encoding in encodings_to_try:
                                try:
                                    decoded = entry_pathname.decode(encoding)
                                    logger.debug(f"Decoded with {encoding}: {decoded}")
                                    break
                                except UnicodeDecodeError:
                                    continue
                            
                            # If all attempts failed, use a fallback with 'ignore' error handling
                            if decoded is None:
                                decoded = entry_pathname.decode('iso-8859-1', errors='ignore')
                                logger.debug(f"Decoded with iso-8859-1 (with ignore): {decoded}")
                                
                        # Log each specific accented character for debugging
                        for i, char in enumerate(decoded):
                            if not (32 <= ord(char) <= 126):  # non-ASCII character
                                logger.debug(f"Character at position {i}: '{char}' (Unicode: U+{ord(char):04X})")
                        
                        # Store original for comparison
                        original_decoded = decoded
                        
                        # Character-by-character conversion approach
                        # This mapping specifically handles common encoding issues with Spanish characters
                        char_mapping = {
                            # Non-breaking space often confused with accented characters
                            '\xa0': 'á',  # This specific case maps non-breaking space to 'á'
                            
                            # Common Latin-1/Windows-1252 codes for Spanish accented characters
                            '\xe1': 'á', '\xc1': 'Á',
                            '\xe9': 'é', '\xc9': 'É',
                            '\xed': 'í', '\xcd': 'Í',
                            '\xf3': 'ó', '\xd3': 'Ó',
                            '\xfa': 'ú', '\xda': 'Ú',
                            '\xf1': 'ñ', '\xd1': 'Ñ',
                            '\xfc': 'ü', '\xdc': 'Ü',
                            
                            # Currency sign often misinterpreted as 'ñ'
                            '¤': 'ñ',      # Direct currency sign
                            '\xa4': 'ñ',   # Latin-1 currency sign
                            '\u00a4': 'ñ', # Unicode currency sign
                            
                            # Pound symbol often misinterpreted as 'ú'
                            '£': 'ú',      # Direct pound symbol
                            '\xa3': 'ú',   # Latin-1 pound symbol
                            '\u00a3': 'ú', # Unicode pound symbol
                            
                            # UTF-8 double-byte sequences that might appear when incorrectly decoded
                            'Ã¡': 'á', 'Ã\x81': 'Á',
                            'Ã©': 'é', 'Ã\x89': 'É',
                            'Ã­': 'í', 'Ã\x8d': 'Í',
                            'Ã³': 'ó', 'Ã\x93': 'Ó',
                            'Ãº': 'ú', 'Ã\x9a': 'Ú',
                            'Ã±': 'ñ', 'Ã\x91': 'Ñ',
                            'Ã¼': 'ü', 'Ã\x9c': 'Ü',
                            
                            # Additional encodings for 'ú' that might be causing issues
                            '\xc3\xba': 'ú',  # UTF-8 raw bytes
                            '\xfa': 'ú',      # ISO-8859-1/Latin-1
                            '\x81': 'ú',      # Another potential variant
                            '\x97': 'ú',      # Another potential variant
                            'Ãš': 'ú',        # Another potential variant
                            'ú': 'ú',         # Direct mapping to ensure preservation
                            '\u00fa': 'ú',    # Unicode escape sequence
                            
                            # Other common misinterpretations
                            '¢': 'ó', '¡': 'í',
                            '¥': 'Ñ', '±': 'ñ',
                            'Â': '', # Often appears as a prefix to special chars
                            
                            # Spanish punctuation
                            '\xbf': '¿', '\xa1': '¡',
                            
                            # Degree symbol and variants
                            'Â°': '°', '\xB0': '°', '¦': '°', '\xF8': '°',
                            
                            # Ordinal indicators (º, ª) and common misinterpretations
                            '§': 'º',  # Section sign → masculine ordinal
                            '\xa7': 'º', # Raw section sign → masculine ordinal
                            '\xba': 'º', # Correct code for masculine ordinal
                            '\xaa': 'ª', # Feminine ordinal
                            
                            # Apostrophe variants
                            '\u2019': "'", '\x92': "'", '\u2018': "'",  # Right and left single quotation marks
                            
                            # Additional Spanish characters and their misinterpretations
                            '\xb7': '·', # Middle dot (used in Catalan)
                            '\xad': '-', # Soft hyphen
                            
                            # More common encoding problems
                            '\x82': 'é', '\x87': 'ç',
                            '\x91': 'ñ', '\x92': 'ó', '\x93': 'í',
                            '‚': 'é'
                        }
                        
                        # Process the filename character by character
                        result = []
                        i = 0
                        while i < len(decoded):
                            # Check for two-character sequences first (like 'Ã¡')
                            if i < len(decoded) - 1:
                                two_chars = decoded[i:i+2]
                                if two_chars in char_mapping:
                                    result.append(char_mapping[two_chars])
                                    i += 2
                                    continue
                            
                            # Check for single character mapping
                            if decoded[i] in char_mapping:
                                result.append(char_mapping[decoded[i]])
                            else:
                                result.append(decoded[i])
                            i += 1
                        
                        # Create the new decoded string
                        decoded = ''.join(result)
                        
                        # Normalize to composed form
                        decoded = unicodedata.normalize('NFC', decoded)
                        
                        # Log ALL filenames, not just ones with special characters
                        logger.debug(f"Final decoded filename: {decoded}")
                        
                        # Also log any transformations that occurred
                        if original_decoded != decoded:
                            logger.debug(f"Character transformation applied: {original_decoded!r} -> {decoded!r}")
                        
                        entry_pathname = decoded

                    normalized_path = os.path.normpath(entry_pathname)
                    file_name = os.path.basename(normalized_path)
                    # Remove any directory prefix from the filename
                    file_name = file_name.split('\\')[-1]  # Handle Windows-style paths
                    file_name = file_name.split('/')[-1]   # Handle Unix-style paths
                    content = b''.join(entry.get_blocks())
                    files[file_name] = content

                    if file_name.lower().endswith('.pdf'):
                        pdf_count += 1
                        base_name = os.path.splitext(file_name)[0]
                        match = re.match(r'[^_]+_([^_]+)_?', base_name)
                        if match:
                            doc_order = match.group(1)
                            doc_order_to_filename[doc_order] = file_name

            # Find and validate index.json
            index_json = None
            for filename, content in files.items():
                if filename.endswith('.json'):
                    try:
                        index_json = json.loads(content.decode('utf-8'))
                        break
                    except json.JSONDecodeError:
                        return jsonify({
                            "status": True,
                            "validation": {
                                "conclusion": False,
                                "message": f"La validación fue procesada correctamente pero el archivo {filename} no es un JSON válido"
                            }
                        }), 200
                        
            if index_json is None:
                return jsonify({
                    "status": True,
                    "validation": {
                        "conclusion": False,
                        "message": "La validación fue procesada correctamente pero no se encontró el archivo índice JSON en el ZIP"
                    }
                }), 200

            # Validate file count
            total_docs_in_index = sum(len(tramite['documentos']) for tramite in index_json['tramites'])
            actual_pdf_count = len([f for f in files if f.lower().endswith('.pdf')])
            
            file_count_message = None
            if actual_pdf_count < total_docs_in_index:
                file_count_message = f"La validación fue procesada correctamente pero faltan documentos. El índice declara {total_docs_in_index} documentos, pero el ZIP contiene {actual_pdf_count} PDFs"
            elif actual_pdf_count > total_docs_in_index:
                file_count_message = f"La validación fue procesada correctamente pero hay documentos adicionales. El índice declara {total_docs_in_index} documentos, pero el ZIP contiene {actual_pdf_count} PDFs"

            validation_results = []
            tramites = index_json['tramites']
            tramites_processed = []
            tramite_args = []

            for idx, tramite in enumerate(tramites):
                tramite_copy = copy.deepcopy(tramite)
                signature = tramite_copy.pop('firma', '')
                if not signature:
                    return jsonify({
                        "status": True,
                        "validation": {
                            "conclusion": False,
                            "message": f"La validación fue procesada correctamente pero el trámite {tramite.get('secuencia', idx)} no contiene firma digital"
                        }
                    }), 200

                tramites_to_include = tramites_processed + [tramite_copy]
                json_str = copy.deepcopy(index_json)
                json_str['tramites'] = tramites_to_include
                tramites_processed.append(tramite)
                tramite_args.append((idx, json_str, signature, tramite_copy, files, doc_order_to_filename, self.max_workers))

            # Process tramites in parallel
            with ThreadPoolExecutor(max_workers=self.max_workers) as executor:
                futures = {
                    executor.submit(self.process_tramite, *args): idx
                    for idx, args in enumerate(tramite_args)
                }
                results_dict = {}
                for future in futures:
                    idx = futures[future]
                    result = future.result()
                    if 'error' in result:
                        return jsonify({
                            "status": True,
                            "validation": {
                                "conclusion": False,
                                "message": f"La validación fue procesada correctamente pero hubo un error: {result['error']}"
                            }
                        }), 200
                    results_dict[idx] = result

            validation_results = [results_dict[idx] for idx in range(len(tramites))]
            validation = {
                'subresults': validation_results,
                'conclusion': all(result['result_indication'] for result in validation_results),
                'message': ' '.join(result['message'] for result in validation_results)
            }

            if file_count_message:
                validation['conclusion'] = False
                validation['message'] = file_count_message + " " + validation['message']

            return jsonify({
                "status": True,
                "validation": validation
            }), 200

        except libarchive.exception.ArchiveError as e:
            return jsonify({
                "status": True,
                "validation": {
                    "conclusion": False,
                    "message": f"La validación fue procesada correctamente pero hubo un error al leer el archivo ZIP: {str(e)}"
                }
            }), 200
        except Exception as e:
            return jsonify({
                "status": True,
                "validation": {
                    "conclusion": False,
                    "message": f"La validación fue procesada correctamente pero hubo un error inesperado: {str(e)}"
                }
            }), 200

    def process_document(self, doc, files, doc_order_to_filename):
        doc_hash = doc['hash_contenido']
        doc_id = doc['id_documento']
        doc_order = str(doc['orden'])
        result_doc = {
            "orden": doc['orden'],
            "id_documento": doc_id,
            "valid_hash": False,
            "doc_filename": None,
            "signatures": None,
            "not_found": False,
            "invalid_format": False  # Add new field for format validation
        }
        try:
            if doc_order in doc_order_to_filename:
                doc_filename = doc_order_to_filename[doc_order]
                doc_content = files[doc_filename]
                
                # Set the filename regardless of validation outcome
                result_doc["doc_filename"] = doc_filename
                
                # Calculate hash and check validity regardless of validation outcome
                hash_doc = hashlib.sha256(doc_content).hexdigest()
                valid_hash = False if not doc_hash else (hash_doc == doc_hash.lower())
                result_doc["valid_hash"] = valid_hash
                
                docb64 = base64.b64encode(doc_content).decode('utf-8')

                # Validate the document
                try:
                    validation_report = validate_signature_pdf(docb64)
                    if not validation_report:
                        logger.warning(f"No validation report received for document {doc_id}")
                        result_doc["signatures"] = []  # Empty signatures list instead of None
                        return result_doc
                except Exception as e:
                    logger.error(f"Error validating signature in document {doc_id}: {str(e)}")
                    result_doc["signatures"] = []  # Empty signatures list instead of None
                    
                    # Check if this is a format recognition error
                    error_str = str(e)
                    logger.debug(f"Checking error message for format issues: {error_str}")
                    
                    # Look for our special marker or other indicators of format problems
                    if "PDF_FORMAT_ERROR" in error_str or "Document format not recognized" in error_str:
                        result_doc["invalid_format"] = True
                        logger.info(f"Document {doc_id} format not recognized by validation service (explicit marker)")
                    # Fallback: For PDFs, most 500 errors from validation are format issues
                    elif "500 Server Error" in error_str and "validateSignature" in error_str:
                        result_doc["invalid_format"] = True
                        logger.info(f"Document {doc_id} likely has format issues (500 error from validation service): {error_str}")
                    
                    return result_doc
                
                try:
                    result_doc_val = validation_analyze(validation_report)
                    if isinstance(result_doc_val, tuple):
                        signatures, _ = result_doc_val
                    else:
                        signatures = result_doc_val
                    # If no signatures found, that's okay - just use an empty list
                    if not signatures:
                        logger.info(f"No signatures found in document {doc_id}")
                        signatures = []
                except Exception as e:
                    logger.error(f"Error analyzing validation in document {doc_id}: {str(e)}")
                    result_doc["signatures"] = []  # Empty signatures list instead of None
                    return result_doc
                
                result_doc["signatures"] = signatures
            else:
                result_doc['not_found'] = True
        except Exception as e:
            logger.error(f"Error processing document {doc_id}: {str(e)}")
            result_doc['error'] = str(e)
            result_doc["signatures"] = []  # Empty signatures list instead of None
        return result_doc

    def process_tramite(self, index, json_str, signature, tramite, files, doc_order_to_filename, max_workers):
        result = {}
        try:
            # Validate the signature using the prepared json_str and signature
            try:
                validation_report, status_code = validate_signature_json(json_str, signature)
                if status_code != 200 or not validation_report:
                    logger.warning("No validation response received for tramite")
                    return {
                        'secuencia': tramite['secuencia'],
                        'is_valid': False,
                        'certs_valid': False,
                        'signature': [],
                        'docs_validation': [],
                        'docs_not_found': [],
                        'subindication': f"Trámite {tramite['secuencia']}: La validación fue procesada correctamente pero no se recibió respuesta de validación",
                        'result_indication': False,
                        'message': f"Trámite {tramite['secuencia']}: La validación fue procesada correctamente pero no se recibió respuesta de validación"
                    }
            except Exception as e:
                logger.error(f"Error validating tramite signature: {str(e)}")
                return {
                    'secuencia': tramite['secuencia'],
                    'is_valid': False,
                    'certs_valid': False,
                    'signature': [],
                    'docs_validation': [],
                    'docs_not_found': [],
                    'subindication': f"Trámite {tramite['secuencia']}: La validación fue procesada correctamente pero hubo un error en la validación",
                    'result_indication': False,
                    'message': f"Trámite {tramite['secuencia']}: La validación fue procesada correctamente pero hubo un error en la validación"
                }

            try:
                result_tramite = validation_analyze(validation_report)
                if isinstance(result_tramite, tuple):
                    validation_result, _ = result_tramite
                else:
                    validation_result = result_tramite
                if not validation_result:
                    logger.info("No signatures found in tramite")
                    validation_result = []
            except Exception as e:
                logger.error(f"Error analyzing validation in tramite: {str(e)}")
                return {
                    'secuencia': tramite['secuencia'],
                    'is_valid': False,
                    'certs_valid': False,
                    'signature': [],
                    'docs_validation': [],
                    'docs_not_found': [],
                    'subindication': f"Trámite {tramite['secuencia']}: La validación fue procesada correctamente pero hubo un error en el análisis",
                    'result_indication': False,
                    'message': f"Trámite {tramite['secuencia']}: La validación fue procesada correctamente pero hubo un error en el análisis"
                }

            # Get the first signature result since we're processing one at a time
            first_signature = validation_result[0] if validation_result else None
            tested = bool(first_signature.get('valid', False)) if first_signature else False
            certs_validation = first_signature.get('certs_valid', False) if first_signature else False

            docs_validation = []
            docs_not_found = []
            errors = []

            # Process documents in parallel using threads
            with ThreadPoolExecutor(max_workers=max_workers) as executor:
                results = executor.map(
                    lambda doc: self.process_document(doc, files, doc_order_to_filename),
                    tramite['documentos']
                )

            for result_doc in results:
                docs_validation.append(result_doc)
                if result_doc.get('not_found', False):
                    docs_not_found.append({
                        "id_documento": result_doc['id_documento'],
                        "orden": result_doc['orden']
                    })
                if 'error' in result_doc:
                    errors.append(result_doc['error'])

            hashes_valid = []
            hashes_invalid = []
            for doc in docs_validation:
                if not doc['valid_hash']:
                    hashes_invalid.append({"id_documento": doc['id_documento'], "orden": doc['orden']})
                else:
                    hashes_valid.append({"id_documento": doc['id_documento'], "orden": doc['orden']})

            # Construct detailed validation message
            if not validation_result:
                indication = f"Trámite {tramite['secuencia']}: La validación fue procesada correctamente. El trámite no contiene firmas."
                if hashes_invalid:
                    indication += f" Documentos con hash inválido: {', '.join([f'{doc['id_documento']} (orden {doc['orden']})' for doc in hashes_invalid])}."
                result_indication = True  # No signatures is a valid state
            elif not tested:
                if certs_validation:
                    indication = f"Trámite {tramite['secuencia']}: La validación fue procesada correctamente pero la firma digital es inválida."
                    if hashes_invalid:
                        indication += f" Documentos con hash inválido: {', '.join([f'{doc['id_documento']} (orden {doc['orden']})' for doc in hashes_invalid])}."
                    result_indication = False
                else:
                    indication = f"Trámite {tramite['secuencia']}: La validación fue procesada correctamente pero la firma digital y los certificados son inválidos."
                    if hashes_invalid:
                        indication += f" Documentos con hash inválido: {', '.join([f'{doc['id_documento']} (orden {doc['orden']})' for doc in hashes_invalid])}."
                    result_indication = False
            else:
                if not certs_validation:
                    indication = f"Trámite {tramite['secuencia']}: La validación fue procesada correctamente pero los certificados son inválidos."
                    if hashes_invalid:
                        indication += f" Documentos con hash inválido: {', '.join([f'{doc['id_documento']} (orden {doc['orden']})' for doc in hashes_invalid])}."
                    result_indication = False
                else:
                    if hashes_invalid:
                        indication = f"Trámite {tramite['secuencia']}: La validación fue procesada correctamente pero hay documentos con hash inválido: {', '.join([f'{doc['id_documento']} (orden {doc['orden']})' for doc in hashes_invalid])}."
                        result_indication = False
                    else:
                        indication = f"Trámite {tramite['secuencia']}: La validación fue procesada correctamente y todos los elementos son válidos."
                        result_indication = True

            result = {
                'secuencia': tramite['secuencia'],
                'is_valid': tested,
                'certs_valid': certs_validation,
                'signature': validation_result,  # Return the full validation result
                'docs_validation': docs_validation,
                'docs_not_found': docs_not_found,
                'subindication': indication,
                'result_indication': result_indication,
                'message': indication
            }
            return result
        except Exception as e:
            logger.error(f"Error processing tramite: {str(e)}")
            return {
                'secuencia': tramite.get('secuencia', 'unknown'),
                'is_valid': False,
                'certs_valid': False,
                'signature': [],
                'docs_validation': [],
                'docs_not_found': [],
                'subindication': f"Error en el procesamiento del trámite: {str(e)}",
                'result_indication': False,
                'message': f"Error en el procesamiento del trámite: {str(e)}"
            }
