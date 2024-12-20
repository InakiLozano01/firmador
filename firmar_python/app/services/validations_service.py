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
            signatures = validation_analyze(report)
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
            
        Raises:
            InvalidSignatureDataError: For validation-related errors
        """
        logger.info("Starting JADES signatures validation")
        validation_results = []
        errors_stack = []
        data_original = copy.deepcopy(data)
        
        try:
            logger.debug(f"Processing {len(data.get('tramites', []))} tramites")
            tramites = data['tramites']

            for i, tramite in enumerate(tramites):
                logger.debug(f"Processing tramite {i+1}")
                try:
                    # Create a copy of data up to current tramite
                    json_str = copy.deepcopy(data)
                    json_str['tramites'] = tramites[:i+1]  # Include all tramites up to current
                    
                    # Get current tramite's signature and remove it for validation
                    current_tramite = json_str['tramites'][-1]
                    signature = current_tramite.pop('firma', '')
                    
                    if not signature or signature == '' or signature is None:
                        error = {
                            "secuencia": tramite.get('secuencia', i),
                            "message": "Error al obtener la firma del trámite. Posiblemente el trámite no se haya firmado"
                        }
                        logger.error(f"Missing signature in tramite {tramite.get('secuencia', i)}")
                        errors_stack.append(error)
                        continue
                except Exception as e:
                    error = {
                        "secuencia": tramite.get('secuencia', i),
                        "message": f"Error procesando firma del trámite: {str(e)}",
                        "stack": str(e.__traceback__)
                    }
                    logger.error(f"Error processing tramite {tramite.get('secuencia', i)}: {str(e)}", exc_info=True)
                    errors_stack.append(error)
                    continue
            
                if errors_stack:
                    return None, data_original, False, "Error al procesar las firmas de los trámites", errors_stack

                try:
                    logger.debug("Validating JADES signature")
                    validation_report = validate_signature_json(json_str, signature)
                    if not validation_report:
                        error = {
                            "message": "No se recibió respuesta de validación JADES",
                            "details": "La validación no retornó resultados"
                        }
                        logger.error("Empty validation response from JADES validation")
                        errors_stack.append(error)
                        return None, data_original, False, "Error en la validación JADES", errors_stack
                    logger.debug("JADES signature validation completed")
                except Exception as e:
                    error = {
                        "message": f"Error al validar JADES: {str(e)}",
                        "stack": str(e.__traceback__),
                        "details": "Error en validate_signature_json"
                    }
                    logger.error(f"Failed to validate JADES signature: {str(e)}", exc_info=True)
                    errors_stack.append(error)
                    return None, data_original, False, "Error en la validación JADES", errors_stack

                try:
                    logger.debug("Analyzing JADES validation result")
                    validation_result = validation_analyze(validation_report)
                    if not validation_result:
                        error = {
                            "message": "No se encontraron firmas válidas en la validación JADES",
                            "details": "validation_analyze no retornó resultados"
                        }
                        logger.error("No valid signatures found in JADES validation")
                        errors_stack.append(error)
                        return None, data_original, False, "No se encontraron firmas válidas", errors_stack
                    logger.debug("JADES validation analysis completed")
                except Exception as e:
                    error = {
                        "message": f"Error al analizar validación JADES: {str(e)}",
                        "stack": str(e.__traceback__),
                        "details": "Error en validation_analyze"
                    }
                    logger.error(f"Failed to analyze JADES validation result: {str(e)}", exc_info=True)
                    errors_stack.append(error)
                    return None, data_original, False, "Error al analizar la validación", errors_stack

                first_signature = validation_result[0] if validation_result else None
                if not first_signature:
                    error = {
                        "message": "No se encontraron firmas para validar en JADES",
                        "details": "No se encontró la primera firma en los resultados"
                    }
                    logger.error("No signatures found to validate in JADES")
                    errors_stack.append(error)
                    return None, data_original, False, "No se encontraron firmas para validar", errors_stack

                tested = bool(first_signature.get('valid', False))
                certs_validation = first_signature.get('certs_valid', False)
                indication = True if certs_validation and tested else False

                validation_results.append({
                    'secuencia': tramite['secuencia'],
                    'is_valid': tested,
                    'certs_valid': certs_validation,
                    'subindication': indication,
                    'signature': validation_result
                })

            validation = {
                'subresults': validation_results,
                'conclusion': all(result['subindication'] for result in validation_results)
            }

            logger.info("JADES validation completed successfully")
            return validation, data_original, True, "Validación completada correctamente", errors_stack

        except Exception as e:
            error = {
                "message": f"Error inesperado en la validación JADES: {str(e)}",
                "stack": str(e.__traceback__),
                "details": "Error general en validate_signatures_jades"
            }
            logger.error(f"Unexpected error in JADES validation: {str(e)}", exc_info=True)
            errors_stack.append(error)
            return None, data_original, False, "Error inesperado en la validación", errors_stack
    
    def validate_expediente(self, path):
        try:
            files = {}
            doc_order_to_filename = {}
            pdf_count = 0
            
            # Extract and process files from ZIP
            with libarchive.file_reader(path) as archive:
                for entry in archive:
                    if entry.isdir:
                        continue
                        
                    entry_pathname = entry.pathname
                    if isinstance(entry_pathname, bytes):
                        try:
                            entry_pathname = entry_pathname.decode('utf-8')
                        except UnicodeDecodeError:
                            entry_pathname = entry_pathname.decode('latin-1')

                    entry_path = unicodedata.normalize('NFKD', entry_pathname).encode('ascii', 'ignore').decode('ascii')
                    normalized_path = os.path.normpath(entry_path)
                    file_name = os.path.basename(normalized_path)
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
            "not_found": False
        }
        try:
            if doc_order in doc_order_to_filename:
                doc_filename = doc_order_to_filename[doc_order]
                doc_content = files[doc_filename]
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
                    return result_doc
                
                try:
                    signatures = validation_analyze(validation_report)
                    # If no signatures found, that's okay - just use an empty list
                    if not signatures:
                        logger.info(f"No signatures found in document {doc_id}")
                        signatures = []
                except Exception as e:
                    logger.error(f"Error analyzing validation in document {doc_id}: {str(e)}")
                    result_doc["signatures"] = []  # Empty signatures list instead of None
                    return result_doc
                
                hash_doc = hashlib.sha256(doc_content).hexdigest()
                if not doc_hash:
                    valid_hash = False
                else:
                    valid_hash = (hash_doc == doc_hash.lower())

                result_doc.update({
                    "valid_hash": valid_hash,
                    "doc_filename": doc_filename,
                    "signatures": signatures
                })
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
                validation_report = validate_signature_json(json_str, signature)
                if not validation_report:
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
                validation_result = validation_analyze(validation_report)
                if not validation_result:
                    logger.info("No signatures found in tramite")
                    validation_result = []
            except Exception as e:
                logger.error(f"Error analyzing tramite validation: {str(e)}")
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
