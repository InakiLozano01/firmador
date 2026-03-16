import os
import logging
import time as _time
from app.services.validations_service import ValidationsService
from app.exceptions import validation_exc
from app.services.observability import SUBJECT_ERROR, subject_scope

logger = logging.getLogger(__name__)

class ValidationsController:
    def __init__(self):
        self.service = ValidationsService()
        logger.debug("ValidationsController initialized")

    def validate_signatures_pdf(self, pdfs, operation_id=None):
        logger.info("Starting PDF signatures validation")
        logger.debug(f"Processing {len(pdfs)} PDFs")
        
        results = []
        errors = []
        success = True
        message = "Validación completada correctamente"
        
        for i, pdf in enumerate(pdfs):
            doc_id = pdf.get('id_documento')
            t0 = _time.monotonic()
            logger.debug(f"Validating PDF {i+1}/{len(pdfs)} with ID: {doc_id}")
            with subject_scope("document", str(doc_id), display_name=f"Documento {doc_id}", attrs={"operation_key": "validate.pdf"}) as tracked_subject:
                try:
                    service_response = self.service.validate_signatures_pdf(pdf)
                    results.append({
                        "id_documento": pdf['id_documento'],
                        "signatures": service_response
                    })
                except Exception as e:
                    elapsed = int((_time.monotonic() - t0) * 1000)
                    logger.error(f"Error validating PDF {i+1}: {str(e)}", exc_info=True)
                    errors.append({
                        "id_documento": doc_id,
                        "message": str(e)
                    })
                    success = False
                    message = "Error al validar algunos documentos"
                    tracked_subject.set_status(
                        SUBJECT_ERROR,
                        error_message=str(e)[:500],
                        attrs={"elapsed_ms": elapsed, "error_class": type(e).__name__},
                    )
        
        if not success:
            logger.warning(f"Validation completed with {len(errors)} errors")
        else:
            logger.info(f"Validation completed successfully for {len(results)} PDFs")
            
        return results, errors, success, message
    
    def validate_signatures_jades(self, data, operation_id=None):
        logger.info("Starting JADES signatures validation")
        t0 = _time.monotonic()
        expediente_key = "unknown"
        if isinstance(data, dict):
            required_keys = {"numero", "anio", "codigo", "letra"}
            if required_keys.issubset(data.keys()):
                expediente_key = f"{data['numero']}/{data['anio']}/{data['codigo']}/{data['letra']}"

        with subject_scope("expediente", expediente_key, display_name=expediente_key, attrs={"operation_key": "validate.jades"}) as tracked_subject:
            try:
                validation, data_original, success, message, errors = self.service.validate_signatures_jades(data)
                elapsed = int((_time.monotonic() - t0) * 1000)

                if not success:
                    logger.warning(f"JADES validation failed: {message}")
                    tracked_subject.set_status(
                        SUBJECT_ERROR,
                        error_message=message[:500],
                        attrs={"elapsed_ms": elapsed, "errors": errors},
                    )
                    return None, None, False, message, errors

                logger.info("JADES signatures validation completed successfully")
                return validation, data_original, True, message, errors

            except Exception as e:
                elapsed = int((_time.monotonic() - t0) * 1000)
                logger.error(f"Error validating JADES signatures: {str(e)}", exc_info=True)
                tracked_subject.set_status(
                    SUBJECT_ERROR,
                    error_message=str(e)[:500],
                    attrs={"elapsed_ms": elapsed, "error_class": type(e).__name__},
                )
                return None, None, False, f"Error inesperado al validar JADES: {str(e)}", [{
                    "message": str(e),
                    "stack": str(e.__traceback__),
                    "details": "Error general en validate_signatures_jades controller"
                }]
        
    def validate_expediente(self, path, operation_id=None):
        logger.info("Starting expediente validation")
        logger.debug(f"Validating expediente at path: {path}")
        t0 = _time.monotonic()
        expediente_key = os.path.basename(path)
        with subject_scope("expediente", expediente_key, display_name=expediente_key, attrs={"path": path, "operation_key": "validate.expediente"}) as tracked_subject:
            try:
                service_response, code = self.service.validate_expediente(path)
                logger.info(f"Expediente validation completed with code: {code}")
                return service_response, code
            except Exception as e:
                elapsed = int((_time.monotonic() - t0) * 1000)
                logger.error(f"Error validating expediente: {str(e)}", exc_info=True)
                tracked_subject.set_status(
                    SUBJECT_ERROR,
                    error_message=str(e)[:500],
                    attrs={"elapsed_ms": elapsed, "error_class": type(e).__name__, "path": path},
                )
                raise validation_exc.InvalidSignatureDataError(f"Error al validar expediente: {str(e)}")
    
            

