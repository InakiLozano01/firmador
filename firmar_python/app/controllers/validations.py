import logging
from app.services.validations_service import ValidationsService
from app.exceptions import validation_exc

# Configure logging
logger = logging.getLogger(__name__)

class ValidationsController:
    def __init__(self):
        self.service = ValidationsService()
        logger.debug("ValidationsController initialized")

    def validate_signatures_pdf(self, pdfs):
        logger.info("Starting PDF signatures validation")
        logger.debug(f"Processing {len(pdfs)} PDFs")
        
        results = []
        errors = []
        success = True
        message = "Validación completada correctamente"
        
        for i, pdf in enumerate(pdfs):
            logger.debug(f"Validating PDF {i+1}/{len(pdfs)} with ID: {pdf.get('id_documento')}")
            try:
                service_response = self.service.validate_signatures_pdf(pdf)
                results.append({
                    "id_documento": pdf['id_documento'],
                    "signatures": service_response
                })
                logger.debug(f"Successfully validated PDF {i+1}")
            except Exception as e:
                logger.error(f"Error validating PDF {i+1}: {str(e)}", exc_info=True)
                errors.append({
                    "id_documento": pdf.get('id_documento'),
                    "message": str(e)
                })
                success = False
                message = "Error al validar algunos documentos"
        
        if not success:
            logger.warning(f"Validation completed with {len(errors)} errors")
        else:
            logger.info(f"Validation completed successfully for {len(results)} PDFs")
            
        return results, errors, success, message
    
    def validate_signatures_jades(self, data):
        """
        Validate JADES signatures with error handling.
        
        Args:
            data: The data containing tramites to validate
            
        Returns:
            tuple: (validation_result, original_data, success, message, errors)
        """
        logger.info("Starting JADES signatures validation")
        try:
            validation, data_original, success, message, errors = self.service.validate_signatures_jades(data)
            
            if not success:
                logger.warning(f"JADES validation failed: {message}")
                logger.debug(f"Validation errors: {errors}")
                return None, None, False, message, errors
            
            logger.info("JADES signatures validation completed successfully")
            return validation, data_original, True, message, errors
            
        except Exception as e:
            logger.error(f"Error validating JADES signatures: {str(e)}", exc_info=True)
            return None, None, False, f"Error inesperado al validar JADES: {str(e)}", [{
                "message": str(e),
                "stack": str(e.__traceback__),
                "details": "Error general en validate_signatures_jades controller"
            }]
        
    def validate_expediente(self, path):
        logger.info("Starting expediente validation")
        logger.debug(f"Validating expediente at path: {path}")
        try:
            service_response, code = self.service.validate_expediente(path)
            logger.info(f"Expediente validation completed with code: {code}")
            return service_response, code
        except Exception as e:
            logger.error(f"Error validating expediente: {str(e)}", exc_info=True)
            raise validation_exc.InvalidSignatureDataError(f"Error al validar expediente: {str(e)}")
    
            


