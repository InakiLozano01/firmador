import logging

from app.services.signatures_service import SignaturesService

logger = logging.getLogger(__name__)


class DocumentoExternoController:
    def __init__(self, service=None):
        self.service = service or SignaturesService()

    def init_documento_externo_electronico(self, pdfs):
        return self._run_init(pdfs, digital=False, certificates=None)

    def init_documento_externo_digital(self, pdfs, certificates):
        return self._run_init(pdfs, digital=True, certificates=certificates)

    def end_documento_externo_digital(self, pdfs, certificates):
        docs_signed = []
        docs_not_signed = []
        signed_pdfs = []
        errors_stack = []
        seen_ids = set()
        success = True
        message = "Firma completada correctamente"
        finalized_count = 0

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
                signed_id, error, signed_pdf = self.service.end_documento_externo_digital(pdf, certificates)
                if error is None:
                    docs_signed.append(signed_id)
                    signed_pdfs.append(signed_pdf)
                else:
                    if error.pop("finalized", False):
                        finalized_count += 1
                    errors_stack.append(error)
                    docs_not_signed.append(error.get("id_documento", id_documento))
                    success = False
                    message = "Error al procesar algunos documentos"
            except Exception as exc:
                logger.error("documento externo end item failed", extra={"id_documento": id_documento}, exc_info=True)
                errors_stack.append({"id_documento": id_documento, "message": str(exc)})
                docs_not_signed.append(id_documento)
                success = False
                message = "Error al procesar algunos documentos"

        replay_conflict = bool(errors_stack) and not docs_signed and finalized_count == len(errors_stack)
        return docs_signed, docs_not_signed, signed_pdfs, errors_stack, success, message, replay_conflict

    def _run_init(self, pdfs, *, digital, certificates):
        docs_signed = []
        docs_not_signed = []
        payloads = []
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
                if digital:
                    signed_id, error, payload = self.service.init_documento_externo_digital(pdf, certificates)
                else:
                    signed_id, error, payload = self.service.sign_documento_externo_electronico(pdf)
                if error is None:
                    docs_signed.append(signed_id)
                    payloads.append(payload)
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

        return docs_signed, docs_not_signed, payloads, errors_stack, success, message
