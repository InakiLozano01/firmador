from firmar_python.app.services.validations_service import ValidationsService
import app.exceptions.validation_exc as validation_exc

class ValidationsController:
    def __init__(self):
        self.service = ValidationsService()

    def validate_signatures_pdf(self, pdfs):
        results = []
        for pdf in pdfs:
            try:
                service_response = self.service.validate_signatures_pdf(pdf)
                results.append({
                    "id_documento": pdf['id_documento'],
                    "signatures": service_response
                })
            except Exception as e:
                raise validation_exc.InvalidSignatureDataError("Error al validar PDFs: " + str(e))
        return results
    
    def validate_signatures_jades(self, data):
        try:
            validation, data_original = self.service.validate_signatures_jades(data)
            return validation, data_original
        except Exception as e:
            raise validation_exc.InvalidSignatureDataError("Error al validar JADES: " + str(e))
        
    def validate_expediente(self, path):
        try:
            service_response, code = self.service.validate_expediente(path)
            return service_response, code
        except Exception as e:
            raise validation_exc.InvalidSignatureDataError("Error al validar expediente: " + str(e))
    
            


