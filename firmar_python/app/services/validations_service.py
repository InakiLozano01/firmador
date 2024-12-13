from app.utils.validation_utils import process_signature, validation_analyze
from app.services.dss.dss_valid import validate_signature_pdf, validate_signature_json
import copy
import app.exceptions.validation_exc as validation_exc
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

class ValidationsService:
    def __init__(self):
        cpu_count = multiprocessing.cpu_count()
        self.max_workers = cpu_count * 2/3  # Adjust based on testing

    def validate_signatures_pdf(self, pdf):
        pdf_b64 = pdf['pdf']
        id_doc = pdf['id_documento']
        try:
            report = validate_signature_pdf(pdf_b64)
        except Exception as e:
            raise validation_exc.InvalidSignatureDataError("Error al validar PDF: Error en validate_pdf: id_doc: " + id_doc)
        try:
            signatures = validation_analyze(report)
        except Exception as e:
            raise validation_exc.InvalidSignatureDataError("Error al validar PDF: Error en validation_analyze: id_doc: " + id_doc)
        return signatures
    
    def validate_signatures_jades(self, data):
        validation_results = []
        data_original = copy.deepcopy(data)
        for tramite in reversed(data['tramites']):
            signature = tramite.pop('firma', '')
            if not signature or signature == '' or signature is None:
                raise validation_exc.InvalidSignatureDataError("Error al obtener la firma del tramite. Posiblemente el tramite no se haya firmado")
        json_str = copy.deepcopy(data)
        try:
            valid = validate_signature_json(json_str, signature)
        except Exception as e:
            raise validation_exc.InvalidSignatureDataError("Error al validar JADES: Error en validate_signature")

        try:
            validation_result = validation_analyze(valid)
        except Exception as e:
            raise validation_exc.InvalidSignatureDataError("Error al validar JADES: Error en validation_analyze")
        
        tested = bool(validation_result[0]['valid'])
        certs_validation = validation_result[0]['certs_valid']
        indication = True if certs_validation and tested else False

        validation_results.append({
            'secuencia': tramite['secuencia'],
            'is_valid': tested,
            'certs_valid': certs_validation,
            'subindication': indication,
            'signature': validation_result
        })

        validation_results.reverse()
        validation = {}
        validation['subresults'] = validation_results

        for result in validation_results:
            total = bool(result['subindication'])
            if not total:
                break

        validation['conclusion'] = total

        return validation, data_original
    
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

    def process_document(doc, files, doc_order_to_filename):
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
                report, code = validate_signature_pdf(docb64)
                if code != 200:
                    raise Exception(f"Error de validación de firma en documento {doc_id}")
                signatures, code = validation_analyze(report)
                if code != 200:
                    raise Exception(f"Error de análisis de validación en documento {doc_id}")
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
            result_doc['error'] = str(e)
        return result_doc

    def process_tramite(self, index, json_str, signature, tramite, files, doc_order_to_filename, max_workers):
        result = {}
        try:
            # Validate the signature using the prepared json_str and signature
            valid, code = validate_signature_json(json_str, signature)
            if code != 200:
                return {"error": "Error en la validación de firma del trámite"}

            validation_result, code = validation_analyze(valid)
            if code != 200:
                return {"error": "Error en el análisis de validación del trámite"}

            tested = bool(validation_result[0]['valid'])
            certs_validation = validation_result[0]['certs_valid']

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

            if errors:
                return {"error": errors[0]}

            hashes_valid = []
            hashes_invalid = []
            for doc in docs_validation:
                if not doc['valid_hash']:
                    hashes_invalid.append({"id_documento": doc['id_documento'], "orden": doc['orden']})
                else:
                    hashes_valid.append({"id_documento": doc['id_documento'], "orden": doc['orden']})

            # Construct detailed validation message
            if not tested:
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
                'signature': validation_result,
                'docs_validation': docs_validation,
                'docs_not_found': docs_not_found,
                'subindication': indication,
                'result_indication': result_indication,
                'message': indication
            }
            return result
        except Exception as e:
            return {"error": f"Error en el procesamiento del trámite: {str(e)}"}
