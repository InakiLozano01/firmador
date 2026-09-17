import logging

from app.services.signatures_service import SignaturesService

logger = logging.getLogger(__name__)


class DocumentoExternoController:
    def __init__(self, service=None):
        self.service = service or SignaturesService()

    def init_documento_externo_electronico(self, pdfs):
        docs_signed = []
        docs_not_signed = []
        signed_pdfs = []
        errors_stack = []
        seen_ids = set()
        success = True
        message = "Firma iniciada correctamente"

        for pdf in pdfs:
            id_documento = pdf.get("id_documento")
            if id_documento in seen_ids:
                errors_stack.append({
                    "id_documento": id_documento,
                    "message": "id_documento duplicado en el lote.",
                })
                docs_not_signed.append(id_documento)
                success = False
                message = "Error al procesar algunos documentos"
                continue
            seen_ids.add(id_documento)
            try:
                signed_id, error, signed_pdf = self.service.sign_documento_externo_electronico(pdf)
                if error is None:
                    docs_signed.append(signed_id)
                    signed_pdfs.append(signed_pdf)
                else:
                    errors_stack.append(error)
                    docs_not_signed.append(error.get("id_documento", id_documento))
                    success = False
                    message = "Error al procesar algunos documentos"
            except Exception as exc:
                logger.error("documento externo item failed", extra={"id_documento": id_documento}, exc_info=True)
                errors_stack.append({"id_documento": id_documento, "message": str(exc)})
                docs_not_signed.append(id_documento)
                success = False
                message = "Error al procesar algunos documentos"

        return docs_signed, docs_not_signed, signed_pdfs, errors_stack, success, message
