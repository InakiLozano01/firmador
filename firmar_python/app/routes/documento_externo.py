import logging
import os

from flask import jsonify, request

from app.config.settings import settings
from app.controllers.documento_externo import DocumentoExternoController
from app.services import observability as observability_mod

logger = logging.getLogger(__name__)
_controller = DocumentoExternoController()

OPERATION_PARTIAL_ERROR = getattr(observability_mod, "OPERATION_PARTIAL_ERROR", "OPERATION_PARTIAL_ERROR")
observe_http_operation = getattr(
    observability_mod,
    "observe_http_operation",
    lambda _key: (lambda fn: fn),
)
update_operation = getattr(observability_mod, "update_operation", lambda **_kwargs: None)


def _expected_api_key():
    return os.getenv("FIRMA_EXTERNA_API_KEY") or settings.FIRMA_EXTERNA_API_KEY


def _unauthorized():
    return jsonify({
        "status": False,
        "message": "API key inválida",
        "errors": [{"message": "Unauthorized"}],
    }), 401


def _empty_pdfs():
    return jsonify({
        "status": False,
        "message": "El lote no puede estar vacío",
        "errors": [{"message": "pdfs vacío"}],
    }), 400


def _certificates_required():
    return jsonify({
        "status": False,
        "message": "Firma Digital requiere certificates",
        "errors": [{"message": "certificates requerido"}],
    }), 400


def _has_certificates(data):
    return "certificates" in data and bool(data.get("certificates"))


def _lote_response(docs_signed, docs_not_signed, errors_stack, success, message, **extra):
    if errors_stack:
        update_operation(
            operation_status=OPERATION_PARTIAL_ERROR,
            error_message=f"{len(errors_stack)} doc(s) failed",
        )
    body = {
        "status": success,
        "message": message,
        "docsSigned": docs_signed,
        "docsNotSigned": docs_not_signed,
        "errors": errors_stack,
    }
    body.update(extra)
    return jsonify(body), 200


def register_documento_externo_routes(app):
    @app.route("/firmaexterna", methods=["POST"])
    @observe_http_operation("sign.pdf.externo.init")
    def firmaexterna():
        if request.headers.get("X-API-Key") != _expected_api_key() or not _expected_api_key():
            return _unauthorized()

        data = request.get_json(silent=True) or {}
        pdfs = data.get("pdfs")
        if not isinstance(pdfs, list) or len(pdfs) == 0:
            return _empty_pdfs()

        if any(isinstance(pdf, dict) and "firma_digital" in pdf for pdf in pdfs):
            return jsonify({
                "status": False,
                "message": "firma_digital es solo a nivel de lote",
                "errors": [{"message": "firma_digital no permitido en el ítem"}],
            }), 400

        firma_digital = data.get("firma_digital")
        if firma_digital is True:
            if not _has_certificates(data):
                return _certificates_required()
            update_operation(batch_size=len(pdfs))
            docs_signed, docs_not_signed, data_to_sign, errors_stack, success, message = (
                _controller.init_documento_externo_digital(pdfs, data.get("certificates"))
            )
            return _lote_response(
                docs_signed,
                docs_not_signed,
                errors_stack,
                success,
                message,
                dataToSign=data_to_sign,
            )

        if firma_digital is not False:
            return jsonify({
                "status": False,
                "message": "firma_digital debe ser true o false",
                "errors": [{"message": "firma_digital inválido"}],
            }), 400

        if "certificates" in data:
            return jsonify({
                "status": False,
                "message": "Firma Electrónica no admite certificates",
                "errors": [{"message": "certificates no permitido"}],
            }), 400

        update_operation(batch_size=len(pdfs))
        docs_signed, docs_not_signed, signed_pdfs, errors_stack, success, message = (
            _controller.init_documento_externo_electronico(pdfs)
        )
        return _lote_response(
            docs_signed,
            docs_not_signed,
            errors_stack,
            success,
            message,
            signedPdfs=signed_pdfs,
        )

    @app.route("/firmaexternaend", methods=["POST"])
    @observe_http_operation("sign.pdf.externo.finalize")
    def firmaexternaend():
        if request.headers.get("X-API-Key") != _expected_api_key() or not _expected_api_key():
            return _unauthorized()

        data = request.get_json(silent=True) or {}
        if "firma_digital" in data:
            return jsonify({
                "status": False,
                "message": "firma_digital no se envía en /firmaexternaend",
                "errors": [{"message": "firma_digital no permitido"}],
            }), 400

        pdfs = data.get("pdfs")
        if not isinstance(pdfs, list) or len(pdfs) == 0:
            return _empty_pdfs()

        if not _has_certificates(data):
            return _certificates_required()

        update_operation(batch_size=len(pdfs))
        docs_signed, docs_not_signed, signed_pdfs, errors_stack, success, message, replay_conflict = (
            _controller.end_documento_externo_digital(pdfs, data.get("certificates"))
        )
        if replay_conflict:
            return jsonify({
                "status": False,
                "message": "La firma ya fue finalizada previamente",
                "docsSigned": docs_signed,
                "docsNotSigned": docs_not_signed,
                "errors": errors_stack,
            }), 409
        return _lote_response(
            docs_signed,
            docs_not_signed,
            errors_stack,
            success,
            message,
            signedPdfs=signed_pdfs,
        )
