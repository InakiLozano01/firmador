"""POST /rest/issuer-certs/resolve — registered separately when routes.py cannot be patched."""

import base64
import logging

from cryptography import x509
from cryptography.hazmat.primitives import hashes
from flask import jsonify, request

from app.services.issuer_pool import resolve_issuer_for_child
from app.services.observability import observe_http_operation

logger = logging.getLogger(__name__)


def register_issuer_resolve_routes(app):
    @app.route("/rest/issuer-certs/resolve", methods=["POST"])
    @observe_http_operation("issuer.certs.resolve")
    def issuer_certs_resolve():
        """
        Resuelve el certificado emisor (intermedio/superior) para un certificado hijo usando el pool en disco.
        """
        try:
            data = request.get_json(silent=True) or {}
            b64_child = data.get("childCertificate")
            if not b64_child or not isinstance(b64_child, str):
                return jsonify(
                    {"status": False, "message": "Se requiere childCertificate (DER en base64)."}
                ), 400
            try:
                try:
                    child_der = base64.b64decode(b64_child, validate=True)
                except TypeError:
                    child_der = base64.b64decode(b64_child)
            except Exception:
                return jsonify({"status": False, "message": "childCertificate no es base64 válido."}), 400
            if len(child_der) > 65536:
                return jsonify({"status": False, "message": "Certificado hijo demasiado grande."}), 400
            issuer_der = resolve_issuer_for_child(child_der)
            if not issuer_der:
                return jsonify(
                    {
                        "status": False,
                        "message": "No se encontró emisor en el pool para este certificado.",
                    }
                ), 404
            issuer_cert = x509.load_der_x509_certificate(issuer_der)
            issuer_fp = issuer_cert.fingerprint(hashes.SHA256()).hex().upper()
            return jsonify(
                {
                    "status": True,
                    "issuerCertificate": base64.b64encode(issuer_der).decode("ascii"),
                    "issuerSha256": issuer_fp,
                }
            ), 200
        except Exception as e:
            logger.error("issuer.certs.resolve failed", exc_info=True)
            return jsonify({"status": False, "message": f"Error al resolver emisor: {str(e)}"}), 500
