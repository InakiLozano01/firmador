import logging
from app.utils.validation_utils import process_signature, validation_analyze
from .dss.dss_valid import validate_signature_pdf, validate_signature_json
import copy
from app.exceptions import validation_exc
from app.config.settings import settings
import libarchive
import os
import json
import re
import unicodedata
from concurrent.futures import ThreadPoolExecutor
import threading
import base64
import hashlib
import multiprocessing
from flask import jsonify
from app.services.observability import SUBJECT_ERROR, stage_scope, subject_scope, submit_with_observability_context

# Configure logging
logger = logging.getLogger(__name__)

class ValidationsService:
    def __init__(self):
        self.max_workers = max(1, int(settings.VALIDATION_MAX_WORKERS))
        self._dss_validate_limiter = threading.BoundedSemaphore(max(1, int(settings.DSS_MAX_INFLIGHT_VALIDATE)))
        logger.debug(f"ValidationsService initialized with {self.max_workers} workers")

    @staticmethod
    def _validation_response(message, conclusion=False):
        return jsonify({
            "status": True,
            "validation": {
                "conclusion": conclusion,
                "message": message,
            }
        }), 200

    @staticmethod
    def _decode_archive_entry_name(entry_pathname):
        if isinstance(entry_pathname, bytes):
            for encoding in ("cp1252", "utf-8", "latin-1", "iso-8859-1"):
                try:
                    return entry_pathname.decode(encoding)
                except UnicodeDecodeError:
                    continue
            return entry_pathname.decode("iso-8859-1", errors="ignore")
        return str(entry_pathname)

    @staticmethod
    def _sanitize_archive_name(filename: str) -> str:
        normalized = unicodedata.normalize("NFKC", filename)
        base_name = os.path.basename(os.path.normpath(normalized)).split("\\")[-1].split("/")[-1]
        sanitized = re.sub(r"[^a-zA-Z0-9_.\-() áéíóúÁÉÍÓÚ]", "", base_name).strip()
        return sanitized or "unnamed"

    def _read_archive_files(self, path):
        files = {}
        doc_order_to_filename = {}
        total_entries = 0
        total_bytes = 0
        sanitized_names = {}

        with stage_scope("archive.extract", "Extraer expediente"):
            with libarchive.file_reader(path) as archive:
                for entry in archive:
                    if entry.isdir:
                        continue

                    total_entries += 1
                    if total_entries > settings.MAX_EXPEDIENTE_ARCHIVE_FILES:
                        raise validation_exc.InvalidSignatureDataError(
                            "ZIP_SANITIZE_COLLISION: cantidad de archivos excede el límite permitido"
                        )

                    entry_name = self._decode_archive_entry_name(entry.pathname)
                    sanitized_name = self._sanitize_archive_name(entry_name)
                    if sanitized_name in sanitized_names and sanitized_names[sanitized_name] != entry_name:
                        raise validation_exc.InvalidSignatureDataError(
                            f"ZIP_SANITIZE_COLLISION: colisión al sanitizar {entry_name!r}"
                        )
                    sanitized_names[sanitized_name] = entry_name

                    content = b"".join(entry.get_blocks())
                    total_bytes += len(content)
                    if total_bytes > settings.MAX_EXPEDIENTE_ARCHIVE_BYTES:
                        raise validation_exc.InvalidSignatureDataError(
                            "ZIP_SANITIZE_COLLISION: tamaño del archivo excede el límite permitido"
                        )

                    files[sanitized_name] = content
                    if sanitized_name.lower().endswith(".pdf"):
                        base_name = os.path.splitext(sanitized_name)[0]
                        match = re.match(r"[^_]+_([^_]+)_?", base_name)
                        if match:
                            doc_order_to_filename[match.group(1)] = sanitized_name

        return files, doc_order_to_filename

    def _validate_pdf_report(self, pdf_b64):
        with self._dss_validate_limiter:
            with stage_scope("dss.validate_request", "Validar PDF en DSS"):
                return validate_signature_pdf(pdf_b64)

    def _validate_json_report(self, json_data, signature):
        with self._dss_validate_limiter:
            with stage_scope("dss.validate_request", "Validar JSON en DSS"):
                return validate_signature_json(json_data, signature)

    def validate_signatures_pdf(self, pdf):
        logger.info("Starting PDF signatures validation")
        pdf_b64 = pdf['pdf']
        id_doc = pdf['id_documento']
        logger.debug(f"Processing PDF with ID: {id_doc}")

        try:
            report = self._validate_pdf_report(pdf_b64)
        except Exception as e:
            logger.error(f"Failed to validate PDF signature for document {id_doc}: {str(e)}", exc_info=True)
            raise validation_exc.InvalidSignatureDataError(f"Error al validar PDF: Error en validate_pdf: id_doc: {id_doc}")

        try:
            with stage_scope("validation.analyze", "Analizar validación"):
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
                    with stage_scope("tramite.signature.validate", "Validar firma de tramite"):
                        validation_report, status_code = self._validate_json_report(data, signature)
                        if status_code != 200 or not validation_report:
                            error = {
                                "secuencia": tramite.get('secuencia', i),
                                "message": "Error en la validación de firma",
                                "status_code": status_code
                            }
                            errors_stack.append(error)
                            continue

                    # Analyze validation results
                    with stage_scope("validation.analyze", "Analizar validación"):
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
            logger.info(f"Processing expediente at path: {path}")
            with stage_scope("archive.sanitize", "Sanitizar expediente"):
                files, doc_order_to_filename = self._read_archive_files(path)

            index_json = None
            with stage_scope("index.load", "Cargar indice"):
                for filename, content in files.items():
                    if filename.endswith('.json'):
                        try:
                            index_json = json.loads(content.decode('utf-8'))
                            break
                        except json.JSONDecodeError:
                            return self._validation_response(
                                f"La validación fue procesada correctamente pero el archivo {filename} no es un JSON válido"
                            )
                        
            if index_json is None:
                return self._validation_response(
                    "La validación fue procesada correctamente pero no se encontró el archivo índice JSON en el ZIP"
                )

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
                    return self._validation_response(
                        f"La validación fue procesada correctamente pero el trámite {tramite.get('secuencia', idx)} no contiene firma digital"
                    )

                tramites_to_include = tramites_processed + [tramite_copy]
                json_str = copy.deepcopy(index_json)
                json_str['tramites'] = tramites_to_include
                tramites_processed.append(tramite)
                tramite_args.append((idx, json_str, signature, tramite_copy, files, doc_order_to_filename, self.max_workers))

            with stage_scope("tramites.dispatch", "Procesar tramites"):
                with ThreadPoolExecutor(max_workers=self.max_workers) as executor:
                    futures = {
                        submit_with_observability_context(executor, self.process_tramite, *args): idx
                        for idx, args in enumerate(tramite_args)
                    }
                    results_dict = {}
                    for future in futures:
                        idx = futures[future]
                        result = future.result()
                        if 'error' in result:
                            return self._validation_response(
                                f"La validación fue procesada correctamente pero hubo un error: {result['error']}"
                            )
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

            return jsonify({"status": True, "validation": validation}), 200

        except libarchive.exception.ArchiveError as e:
            return self._validation_response(
                f"La validación fue procesada correctamente pero hubo un error al leer el archivo ZIP: {str(e)}"
            )
        except Exception as e:
            return self._validation_response(
                f"La validación fue procesada correctamente pero hubo un error inesperado: {str(e)}"
            )

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
            with subject_scope("document", str(doc_id), display_name=f"Documento {doc_id}", attrs={"orden": doc_order}) as tracked_subject:
                if doc_order in doc_order_to_filename:
                    doc_filename = doc_order_to_filename[doc_order]
                    doc_content = files[doc_filename]
                    result_doc["doc_filename"] = doc_filename

                    with stage_scope("hash.check", "Validar hash"):
                        hash_doc = hashlib.sha256(doc_content).hexdigest()
                        valid_hash = False if not doc_hash else (hash_doc == doc_hash.lower())
                        result_doc["valid_hash"] = valid_hash

                    docb64 = base64.b64encode(doc_content).decode('utf-8')

                    try:
                        validation_report = self._validate_pdf_report(docb64)
                        if not validation_report:
                            logger.warning(f"No validation report received for document {doc_id}")
                            result_doc["signatures"] = []
                            tracked_subject.set_status(SUBJECT_ERROR, error_message="No validation report received")
                            return result_doc
                    except Exception as e:
                        logger.error(f"Error validating signature in document {doc_id}: {str(e)}")
                        result_doc["signatures"] = []
                        error_str = str(e)
                        logger.debug(f"Checking error message for format issues: {error_str}")

                        if "PDF_FORMAT_ERROR" in error_str or "Document format not recognized" in error_str:
                            result_doc["invalid_format"] = True
                            logger.info(f"Document {doc_id} format not recognized by validation service (explicit marker)")
                        elif "500 Server Error" in error_str and "validateSignature" in error_str:
                            result_doc["invalid_format"] = True
                            logger.info(f"Document {doc_id} likely has format issues (500 error from validation service): {error_str}")

                        tracked_subject.set_status(SUBJECT_ERROR, error_message=error_str[:500])
                        return result_doc

                    try:
                        with stage_scope("validation.analyze", "Analizar validación"):
                            result_doc_val = validation_analyze(validation_report)
                            if isinstance(result_doc_val, tuple):
                                signatures, _ = result_doc_val
                            else:
                                signatures = result_doc_val
                            if not signatures:
                                logger.info(f"No signatures found in document {doc_id}")
                                signatures = []
                    except Exception as e:
                        logger.error(f"Error analyzing validation in document {doc_id}: {str(e)}")
                        result_doc["signatures"] = []
                        tracked_subject.set_status(SUBJECT_ERROR, error_message=str(e)[:500])
                        return result_doc

                    result_doc["signatures"] = signatures
                else:
                    result_doc['not_found'] = True
                    tracked_subject.set_status(SUBJECT_ERROR, error_message="Documento no encontrado en ZIP")
        except Exception as e:
            logger.error(f"Error processing document {doc_id}: {str(e)}")
            result_doc['error'] = str(e)
            result_doc["signatures"] = []
        return result_doc

    def process_tramite(self, index, json_str, signature, tramite, files, doc_order_to_filename, max_workers):
        result = {}
        try:
            # Validate the signature using the prepared json_str and signature
            try:
                with stage_scope("tramite.signature.validate", "Validar firma de tramite"):
                    validation_report, status_code = self._validate_json_report(json_str, signature)
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
                with stage_scope("validation.analyze", "Analizar validación"):
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

            for doc in tramite['documentos']:
                result_doc = self.process_document(doc, files, doc_order_to_filename)
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
