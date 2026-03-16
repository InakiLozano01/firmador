import base64
import json
import logging
import time as _time
from app.services.signatures_service import SignaturesService
from app.services.observability import SUBJECT_ERROR, subject_scope, update_operation

logger = logging.getLogger(__name__)


def _extract_expediente_key(index_data):
    try:
        raw_index = index_data.get("index")
        decoded = json.loads(base64.b64decode(raw_index).decode("utf-8")) if isinstance(raw_index, str) else raw_index
        return f"{decoded['numero']}/{decoded['anio']}/{decoded['codigo']}/{decoded['letra']}"
    except Exception:
        return "unknown"

class SignaturesController:
    def __init__(self):
        self.service = SignaturesService()
        logger.debug("SignaturesController initialized")

    def signature_pdf_loro(self, pdfs, operation_id=None):
        logger.info("Starting PDF signature initialization for loro")
        logger.debug(f"Processing {len(pdfs)} PDFs")
        id_docs_signeds = []
        errors_stack = []
        signed_pdfs = []
        success = True
        message = "Firma iniciada correctamente"
        
        for i, pdf in enumerate(pdfs):
            id_doc = pdf.get('id_doc')
            t0 = _time.monotonic()
            logger.debug(f"Processing PDF {i+1}/{len(pdfs)}")
            with subject_scope("document", str(id_doc), display_name=f"Documento {id_doc}", attrs={"operation_key": "sign.pdf.loro"}) as tracked_subject:
                try:
                    id_doc_signed, error_stack, signed_pdf_base64 = self.service.signature_pdf_loro(pdf)
                    elapsed = int((_time.monotonic() - t0) * 1000)
                    if error_stack is None:
                        if id_doc_signed:
                            id_docs_signeds.append(id_doc_signed)
                        if signed_pdf_base64:
                            signed_pdfs.append(signed_pdf_base64)
                    else:
                        errors_stack.append(error_stack)
                        success = False
                        message = "Error al procesar algunos documentos"
                        tracked_subject.set_status(
                            SUBJECT_ERROR,
                            error_message=str(error_stack)[:500],
                            attrs={"elapsed_ms": elapsed, "error": error_stack},
                        )
                except Exception as e:
                    elapsed = int((_time.monotonic() - t0) * 1000)
                    logger.error(f"Exception during PDF {i+1} signature initialization: {str(e)}", exc_info=True)
                    errors_stack.append({
                        "idDocFailed": id_doc,
                        "message": str(e)
                    })
                    success = False
                    message = "Error al procesar algunos documentos"
                    tracked_subject.set_status(
                        SUBJECT_ERROR,
                        error_message=str(e)[:500],
                        attrs={"elapsed_ms": elapsed, "error_class": type(e).__name__},
                    )
        
        id_docs_signeds.sort()
        docs_not_signed = []
        for error in errors_stack:
            if error.get('idDocFailed'):
                docs_not_signed.append(error['idDocFailed'])
        
        logger.info(f"PDF signature initialization completed. Successful: {len(id_docs_signeds)}, Failed: {len(docs_not_signed)}")
        return id_docs_signeds, docs_not_signed, signed_pdfs, errors_stack, success, message
    
    def init_signature_pdf(self, pdfs, certificates, operation_id=None):
        logger.info("Starting PDF signature initialization")
        logger.debug(f"Processing {len(pdfs)} PDFs")
        
        id_docs_signeds = []
        errors_stack = []
        datas_to_sign = []
        success = True
        message = "Firma iniciada correctamente"

        batch_id = self.service.generate_batch_id(pdfs)
        logger.debug(f"Generated signing batch_id {batch_id} for {len(pdfs)} PDFs")
        update_operation(attrs={"batch_id": batch_id})
        
        for i, pdf in enumerate(pdfs):
            id_doc = pdf.get('id_doc')
            id_user = pdf.get('id_usuario')
            t0 = _time.monotonic()
            logger.debug(f"Processing PDF {i+1}/{len(pdfs)}")
            with subject_scope(
                "document",
                str(id_doc),
                display_name=f"Documento {id_doc}",
                id_user=str(id_user) if id_user is not None else None,
                attrs={"operation_key": "sign.pdf.init", "batch_id": batch_id},
            ) as tracked_subject:
                try:
                    id_doc_signed, error_stack, data_to_sign = self.service.init_signature_pdf(
                        pdf,
                        certificates,
                        batch_id=batch_id
                    )
                    elapsed = int((_time.monotonic() - t0) * 1000)
                    if error_stack is None:
                        if id_doc_signed:
                            id_docs_signeds.append(id_doc_signed)
                        if data_to_sign:
                            datas_to_sign.append(data_to_sign)
                    else:
                        errors_stack.append(error_stack)
                        success = False
                        message = "Error al procesar algunos documentos"
                        tracked_subject.set_status(
                            SUBJECT_ERROR,
                            error_message=str(error_stack)[:500],
                            attrs={"elapsed_ms": elapsed, "error": error_stack},
                        )
                except Exception as e:
                    elapsed = int((_time.monotonic() - t0) * 1000)
                    logger.error(f"Exception during PDF {i+1} signature initialization: {str(e)}", exc_info=True)
                    errors_stack.append({
                        "idDocFailed": id_doc,
                        "message": str(e)
                    })
                    success = False
                    message = "Error al procesar algunos documentos: " + str(errors_stack)
                    tracked_subject.set_status(
                        SUBJECT_ERROR,
                        error_message=str(e)[:500],
                        attrs={"elapsed_ms": elapsed, "error_class": type(e).__name__},
                    )
        
        id_docs_signeds.sort()
        docs_not_signed = []
        for error in errors_stack:
            if error.get('idDocFailed'):
                docs_not_signed.append(error['idDocFailed'])
        
        logger.info(f"PDF signature initialization completed. Successful: {len(id_docs_signeds)}, Failed: {len(docs_not_signed)}")
        return id_docs_signeds, docs_not_signed, datas_to_sign, errors_stack, success, message
    
    def end_signature_pdf(self, pdfs, certificates, operation_id=None):
        logger.info("Starting PDF signature finalization")
        logger.debug(f"Processing {len(pdfs)} PDFs")
        
        id_docs_signeds = []
        errors_stack = []
        
        for i, pdf in enumerate(pdfs):
            id_doc = pdf.get('id_doc', 'unknown')
            id_user = pdf.get('id_usuario')
            t0 = _time.monotonic()
            logger.debug(f"Processing PDF {i+1}/{len(pdfs)}")
            with subject_scope(
                "document",
                str(id_doc),
                display_name=f"Documento {id_doc}",
                id_user=str(id_user) if id_user is not None else None,
                attrs={"operation_key": "sign.pdf.finalize"},
            ) as tracked_subject:
                try:
                    id_doc_signed, error_stack = self.service.end_signature_pdf(pdf, certificates)
                    elapsed = int((_time.monotonic() - t0) * 1000)
                    if error_stack is None:
                        id_docs_signeds.append(id_doc_signed)
                    else:
                        errors_stack.append(error_stack)
                        tracked_subject.set_status(
                            SUBJECT_ERROR,
                            error_message=str(error_stack)[:500],
                            attrs={"elapsed_ms": elapsed, "error": error_stack},
                        )
                except Exception as e:
                    elapsed = int((_time.monotonic() - t0) * 1000)
                    logger.error(f"Exception during PDF {i+1} (ID: {id_doc}) signature finalization: {str(e)}", exc_info=True)
                    errors_stack.append({
                        "idDocFailed": id_doc,
                        "message": str(e)
                    })
                    tracked_subject.set_status(
                        SUBJECT_ERROR,
                        error_message=str(e)[:500],
                        attrs={"elapsed_ms": elapsed, "error_class": type(e).__name__},
                    )
        
        docs_not_signed = []
        for error in errors_stack:
            if error.get('idDocFailed'):
                docs_not_signed.append(error['idDocFailed'])
        
        logger.info(f"PDF signature finalization completed. Successful: {len(id_docs_signeds)}, Failed: {len(docs_not_signed)}")
        return id_docs_signeds, docs_not_signed, errors_stack
    
    def init_sign_jades(self, certificates, indexes_data, data_signature, operation_id=None):
        logger.info("Starting JADES signature initialization")
        logger.debug(f"Processing {len(indexes_data)} indexes")
        
        id_exps_signeds = []
        errors_stack = []
        data_to_sign = []
        index_signeds = []

        for i, index_data in enumerate(indexes_data):
            t0 = _time.monotonic()
            logger.debug(f"Processing index {i+1}/{len(indexes_data)}")
            exp_key = _extract_expediente_key(index_data)
            with subject_scope("expediente", exp_key, display_name=exp_key, attrs={"operation_key": "sign.jades.init"}) as tracked_subject:
                try:
                    id_exp_signed, error_stack, data_to_sign_item, index_signed = self.service.init_sign_jades(index_data, certificates, data_signature)
                    elapsed = int((_time.monotonic() - t0) * 1000)
                    if error_stack is None:
                        if id_exp_signed:
                            id_exps_signeds.append(id_exp_signed)
                        if data_to_sign_item:
                            data_to_sign.append(data_to_sign_item)
                        if index_signed:
                            index_signeds.append(index_signed)
                    else:
                        errors_stack.append(error_stack)
                        tracked_subject.set_status(
                            SUBJECT_ERROR,
                            error_message=str(error_stack)[:500],
                            attrs={"elapsed_ms": elapsed, "error": error_stack},
                        )
                except Exception as e:
                    elapsed = int((_time.monotonic() - t0) * 1000)
                    logger.error(f"Exception during index {i+1} JADES signature initialization: {str(e)}", exc_info=True)
                    errors_stack.append({
                        "idExpFailed": exp_key,
                        "message": f"Error inesperado en init_sign_jades: {str(e)}",
                        "stack": str(e.__traceback__)
                    })
                    tracked_subject.set_status(
                        SUBJECT_ERROR,
                        error_message=str(e)[:500],
                        attrs={"elapsed_ms": elapsed, "error_class": type(e).__name__},
                    )
                    continue
        
        exps_not_signed = []
        for error in errors_stack:
            if error.get('idExpFailed'):
                exps_not_signed.append(error['idExpFailed'])
        
        logger.info(f"JADES signature initialization completed. Successful: {len(id_exps_signeds)}, Failed: {len(exps_not_signed)}")
        return id_exps_signeds, exps_not_signed, data_to_sign, index_signeds, errors_stack
    
    def end_sign_jades(self, certificates, indexes_data, data_signature, operation_id=None):
        logger.info("Starting JADES signature finalization")
        logger.debug(f"Processing {len(indexes_data)} indexes")
        
        id_exps_signeds = []
        errors_stack = []
        index_signeds = []
        
        for i, index_data in enumerate(indexes_data):
            t0 = _time.monotonic()
            logger.debug(f"Processing index {i+1}/{len(indexes_data)}")
            exp_key = _extract_expediente_key(index_data)
            with subject_scope("expediente", exp_key, display_name=exp_key, attrs={"operation_key": "sign.jades.finalize"}) as tracked_subject:
                try:
                    id_exp_signed, error_stack, index_signed = self.service.end_sign_jades(index_data, certificates, data_signature)
                    elapsed = int((_time.monotonic() - t0) * 1000)
                    if error_stack is None:
                        id_exps_signeds.append(id_exp_signed)
                        index_signeds.append(index_signed)
                    else:
                        errors_stack.append(error_stack)
                        tracked_subject.set_status(
                            SUBJECT_ERROR,
                            error_message=str(error_stack)[:500],
                            attrs={"elapsed_ms": elapsed, "error": error_stack},
                        )
                except Exception as e:
                    elapsed = int((_time.monotonic() - t0) * 1000)
                    logger.error(f"Exception during index {i+1} JADES signature finalization: {str(e)}", exc_info=True)
                    tracked_subject.set_status(
                        SUBJECT_ERROR,
                        error_message=str(e)[:500],
                        attrs={"elapsed_ms": elapsed, "error_class": type(e).__name__},
                    )
                    continue
        
        exps_not_signed = []
        for error in errors_stack:
            exps_not_signed.append(error['idExpFailed'])
        
        logger.info(f"JADES signature finalization completed. Successful: {len(id_exps_signeds)}, Failed: {len(exps_not_signed)}")
        return id_exps_signeds, exps_not_signed, index_signeds, errors_stack
