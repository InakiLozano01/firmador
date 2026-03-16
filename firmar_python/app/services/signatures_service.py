import base64
import hashlib
import io
import json
import logging
import time as tiempo
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Optional

from PyPDF2 import PdfReader
from cryptography import x509
from cryptography.hazmat.backends import default_backend

from app.config.state import app_state
from app.exceptions import signature_exc
from app.services.dss.close_pdf import close_pdf
from app.services.dss.dss_json import get_data_to_sign_tapir_jades, sign_document_tapir_jades
from app.services.dss.dss_pdf import (
    get_data_to_sign_certificate,
    get_data_to_sign_token,
    sign_document_certificate,
    sign_document_token,
)
from app.services.local_certs import get_certificate_from_local, get_signature_value_own
from app.services.observability import ENTRY_ERROR, current_operation, record_entry, stage_scope
from app.services.signing_context_store import (
    EntityLock,
    FinalizeClaimResult,
    SigningContextConflictError,
    SigningContextUnavailableError,
    signing_context_store,
)
from app.utils.db import (
    get_number_and_date_then_close,
    get_number_and_date_then_close_project,
    unlock_pdf_and_close_task,
    unlock_pdf_and_close_task_project,
)
from app.utils.image_utils import create_sello_image as create_signature_image, create_signature_image_system
from app.utils.saving import discard_staged_file, promote_staged_file, save_signed_pdf_atomic, write_repair_manifest

logger = logging.getLogger(__name__)

ERROR_CTX_RELEASE_FAILED = "CTX_RELEASE_FAILED"
ERROR_PDF_SAVE_FAILED = "PDF_SAVE_FAILED"
ERROR_PDF_REPAIR_REQUIRED = "PDF_REPAIR_REQUIRED"


class RepairRequiredError(signature_exc.SignatureProcessError):
    pass


@dataclass(frozen=True)
class SigningExecutionContext:
    timestamp_ms: int
    datetimesigned: str
    is_closing: bool


@dataclass(frozen=True)
class DocumentProcessingContext:
    execution: SigningExecutionContext
    source_pdf_sha256: str
    page_count: int


def validate_certificate_expiration(certificates):
    if not certificates or not isinstance(certificates, dict):
        return True, None
    if "certificate" not in certificates:
        return True, None

    try:
        cert_bytes = base64.b64decode(certificates["certificate"])
        cert = x509.load_der_x509_certificate(cert_bytes, default_backend())
        try:
            not_after = cert.not_valid_after_utc
        except AttributeError:
            not_after = cert.not_valid_after
            if not_after.tzinfo is None:
                not_after = not_after.replace(tzinfo=timezone.utc)

        current_time = datetime.now(timezone.utc)
        if not_after <= current_time:
            return False, f"Certificate has expired. Expiration date: {not_after.strftime('%d/%m/%Y %H:%M:%S')}"
        return True, None
    except Exception as exc:
        return False, f"Error validating certificate: {str(exc)}"


class SignaturesService:
    def __init__(self):
        self.signing_context_store = signing_context_store

    @staticmethod
    def generate_batch_id(pdfs):
        doc_ids = [str(pdf.get("id_doc")) for pdf in pdfs if pdf.get("id_doc")]
        first_user = "unknown"
        for pdf in pdfs:
            if pdf.get("id_usuario") is not None:
                first_user = str(pdf.get("id_usuario"))
                break
        return signing_context_store.generate_batch_id(doc_ids, first_user)

    @staticmethod
    def normalize_datetimesigned(datetimesigned: str) -> str:
        try:
            datetime.strptime(datetimesigned, "%d/%m/%Y %H:%M:%S")
            return datetimesigned
        except ValueError:
            dt = datetime.strptime(datetimesigned, "%Y-%m-%d %H:%M:%S")
            return dt.strftime("%d/%m/%Y %H:%M:%S")

    def build_execution_context(self, timestamp_ms: int, datetimesigned: str, is_closing: bool) -> SigningExecutionContext:
        return SigningExecutionContext(
            timestamp_ms=int(timestamp_ms),
            datetimesigned=self.normalize_datetimesigned(datetimesigned),
            is_closing=bool(is_closing),
        )

    def _build_document_context(self, pdf_b64: str, execution: SigningExecutionContext) -> DocumentProcessingContext:
        try:
            pdf_bytes = base64.b64decode(pdf_b64)
            page_count = len(PdfReader(io.BytesIO(pdf_bytes)).pages)
        except Exception as exc:
            raise signature_exc.SignatureValidationError(f"Error al procesar PDF: {str(exc)}") from exc

        return DocumentProcessingContext(
            execution=execution,
            source_pdf_sha256=self.signing_context_store.build_pdf_sha256(pdf_b64),
            page_count=page_count,
        )

    @staticmethod
    def _operation_id_fallback(subject_key: str) -> str:
        operation_id = current_operation().get("operation_id")
        if operation_id:
            return operation_id
        return f"{subject_key}-{int(tiempo.time() * 1000)}"

    @staticmethod
    def _hash_signed_pdf(finalpdf: str) -> str:
        return hashlib.sha256(base64.b64decode(finalpdf)).hexdigest()

    @staticmethod
    def _error_payload(*, id_doc=None, id_exp=None, message: str, details: Optional[str] = None):
        payload = {"message": message}
        if id_doc is not None:
            payload["idDocFailed"] = id_doc
        if id_exp is not None:
            payload["idExpFailed"] = id_exp
        if details:
            payload["details"] = details
        return payload

    def _build_pdf_request_fingerprint(self, *, pdf_b64: str, id_doc, id_user, field_id, is_closing, is_digital) -> str:
        return self.signing_context_store.build_request_fingerprint(
            id_doc=str(id_doc),
            id_user=str(id_user),
            field_id=str(field_id),
            is_closing=bool(is_closing),
            is_digital=bool(is_digital),
            pdf_sha256=self.signing_context_store.build_pdf_sha256(pdf_b64),
        )

    def _claim_pdf_context(self, *, pdf_b64: str, id_doc, id_user, field_id, is_closing, is_digital) -> FinalizeClaimResult:
        fingerprint = self._build_pdf_request_fingerprint(
            pdf_b64=pdf_b64,
            id_doc=id_doc,
            id_user=id_user,
            field_id=field_id,
            is_closing=is_closing,
            is_digital=is_digital,
        )
        with stage_scope("signing_context.claim", "Reclamar contexto de firma"):
            claim = self.signing_context_store.claim_context_for_end(str(id_doc), fingerprint)
        logger.info(
            "signing_context_claim",
            extra={
                "obs_attrs": {
                    "subject_type": "document",
                    "subject_key": str(id_doc),
                    "context_result": claim.result,
                    "attempt_count": (claim.context or {}).get("attempt_count"),
                    "batch_id": (claim.context or {}).get("batch_id"),
                }
            },
        )
        return claim

    def _claim_jades_context(self, *, exp_id: str, id_user, json_b64: str) -> FinalizeClaimResult:
        fingerprint = self.signing_context_store.build_jades_request_fingerprint(
            exp_id=str(exp_id),
            id_user=str(id_user) if id_user is not None else None,
            json_sha256=self.signing_context_store.build_json_sha256(json_b64),
        )
        with stage_scope("signing_context.claim", "Reclamar contexto de firma"):
            claim = self.signing_context_store.claim_jades_context(exp_id, fingerprint)
        logger.info(
            "signing_context_claim",
            extra={
                "obs_attrs": {
                    "subject_type": "expediente",
                    "subject_key": exp_id,
                    "context_result": claim.result,
                    "attempt_count": (claim.context or {}).get("attempt_count"),
                }
            },
        )
        return claim

    def _release_pdf_context_for_retry(self, id_doc, lease_token, error_code, error_message):
        if not lease_token:
            return
        try:
            with stage_scope("signing_context.release", "Liberar contexto de firma"):
                result = self.signing_context_store.release_context_for_retry(
                    str(id_doc),
                    lease_token,
                    error_code=error_code,
                    error_message=error_message[:500] if error_message else None,
                )
            logger.info(
                "signing_context_release",
                extra={
                    "obs_attrs": {
                        "subject_type": "document",
                        "subject_key": str(id_doc),
                        "context_result": result,
                        "error_code": error_code,
                    }
                },
            )
        except Exception:
            logger.error(
                "signing_context_release_failed",
                exc_info=True,
                extra={
                    "obs_attrs": {
                        "subject_type": "document",
                        "subject_key": str(id_doc),
                        "error_code": ERROR_CTX_RELEASE_FAILED,
                    }
                },
            )

    def _release_jades_context_for_retry(self, exp_id, lease_token, error_code, error_message):
        if not lease_token:
            return
        try:
            with stage_scope("signing_context.release", "Liberar contexto de firma"):
                result = self.signing_context_store.release_jades_context_for_retry(
                    exp_id,
                    lease_token,
                    error_code=error_code,
                    error_message=error_message[:500] if error_message else None,
                )
            logger.info(
                "signing_context_release",
                extra={
                    "obs_attrs": {
                        "subject_type": "expediente",
                        "subject_key": exp_id,
                        "context_result": result,
                        "error_code": error_code,
                    }
                },
            )
        except Exception:
            logger.error(
                "signing_context_release_failed",
                exc_info=True,
                extra={
                    "obs_attrs": {
                        "subject_type": "expediente",
                        "subject_key": exp_id,
                        "error_code": ERROR_CTX_RELEASE_FAILED,
                    }
                },
            )

    def _complete_pdf_context(self, id_doc, lease_token):
        if not lease_token:
            return
        try:
            with stage_scope("signing_context.complete", "Completar contexto de firma"):
                result = self.signing_context_store.complete_context_finalize(str(id_doc), lease_token)
            logger.info(
                "signing_context_complete",
                extra={
                    "obs_attrs": {
                        "subject_type": "document",
                        "subject_key": str(id_doc),
                        "context_result": result,
                    }
                },
            )
        except Exception:
            logger.error(
                "signing_context_complete_failed",
                exc_info=True,
                extra={"obs_attrs": {"subject_type": "document", "subject_key": str(id_doc)}},
            )

    def _complete_jades_context(self, exp_id, lease_token):
        if not lease_token:
            return
        try:
            with stage_scope("signing_context.complete", "Completar contexto de firma"):
                result = self.signing_context_store.complete_jades_context_finalize(exp_id, lease_token)
            logger.info(
                "signing_context_complete",
                extra={
                    "obs_attrs": {
                        "subject_type": "expediente",
                        "subject_key": exp_id,
                        "context_result": result,
                    }
                },
            )
        except Exception:
            logger.error(
                "signing_context_complete_failed",
                exc_info=True,
                extra={"obs_attrs": {"subject_type": "expediente", "subject_key": exp_id}},
            )

    def _acquire_entity_lock(self, entity_type: str, entity_id: str, message: str):
        try:
            lock = self.signing_context_store.acquire_entity_lock(entity_type, entity_id)
        except SigningContextUnavailableError as exc:
            raise signature_exc.SignatureProcessError(
                f"Error de infraestructura al obtener bloqueo de concurrencia: {exc}"
            ) from exc

        if lock is None:
            raise signature_exc.SignatureValidationError(message)
        return lock

    def _release_entity_lock(self, lock: Optional[EntityLock]):
        if lock is None:
            return
        try:
            released = self.signing_context_store.release_entity_lock(lock)
            if not released:
                logger.warning(
                    "entity_lock_release_mismatch",
                    extra={"obs_attrs": {"subject_key": lock.entity}},
                )
        except Exception:
            logger.error(
                "entity_lock_release_failed",
                exc_info=True,
                extra={"obs_attrs": {"subject_key": lock.entity}},
            )

    def _build_signature_image(self, *, stamp_text: str, encoded_image_data: str, mode: str, usuario: str, label_signed_by: Optional[str] = None):
        with stage_scope("signature_image.create", "Crear imagen de firma"):
            with stage_scope("signature_image.assets_load", "Cargar recursos de firma"):
                image_data = encoded_image_data
            with stage_scope("signature_image.render", "Renderizar firma"):
                if mode == "yunga":
                    image = create_signature_image_system(
                        stamp_text,
                        image_data,
                        "yunga",
                        usuario=usuario,
                    )
                else:
                    image = create_signature_image(
                        stamp_text,
                        image_data,
                        mode,
                        usuario=usuario,
                        label_signed_by=label_signed_by or "Firmado digitalmente por",
                    )
            with stage_scope("signature_image.encode", "Codificar imagen de firma"):
                return image["data"]

    def _persist_signed_pdf(
        self,
        *,
        finalpdf: str,
        filepath: str,
        hash_doc: str,
        unlock_params: dict,
        id_doc,
        subject_key: str,
        db_finalize,
        lease_token: Optional[str] = None,
    ):
        operation_id = self._operation_id_fallback(subject_key)
        with stage_scope("pdf.persist.stage", "Persistir PDF en staging"):
            staged_file = save_signed_pdf_atomic(finalpdf, filepath, operation_id)

        db_committed = False
        try:
            with stage_scope("task.unlock_close", "Desbloquear y cerrar tarea"):
                db_finalize(unlock_params)
            db_committed = True
        except Exception:
            discard_staged_file(staged_file)
            raise

        try:
            with stage_scope("pdf.persist.promote", "Promover PDF firmado"):
                promote_staged_file(staged_file)
        except Exception as exc:
            manifest_path = write_repair_manifest(
                staged_file,
                id_doc=str(id_doc),
                hash_doc=hash_doc,
                operation_id=operation_id,
                extra={"subject_key": subject_key},
            )
            record_entry(
                entry_kind=ENTRY_ERROR,
                title="PDF repair required",
                message="DB finalization succeeded but PDF promotion failed",
                error_code=ERROR_PDF_REPAIR_REQUIRED,
                error_class=type(exc).__name__,
                attrs={
                    "subject_type": "document",
                    "subject_key": subject_key,
                    "retryable": False,
                    "repair_manifest": manifest_path,
                    "db_committed": db_committed,
                },
            )
            if lease_token:
                self._complete_pdf_context(id_doc, lease_token)
            raise RepairRequiredError(
                f"Error al promover PDF firmado; se generó reparación pendiente: {str(exc)}"
            ) from exc

    def signature_pdf_loro(self, pdf):
        error = None
        pdf_b64 = pdf["pdf"]
        field_id = pdf["firma_lugar"]
        id_doc = pdf["id_doc"]
        fields_to_fill = pdf["fields_to_fill"]

        execution = self.build_execution_context(
            timestamp_ms=int(tiempo.time() * 1000),
            datetimesigned=datetime.now().strftime("%d/%m/%Y %H:%M:%S"),
            is_closing=False,
        )

        try:
            custom_image = self._build_signature_image(
                stamp_text=f"TRIBUNAL DE CUENTAS TUCUMÁN\n{execution.datetimesigned}",
                encoded_image_data=app_state.encoded_image_yunga.get("data")
                if isinstance(app_state.encoded_image_yunga, dict)
                else app_state.encoded_image_yunga,
                mode="yunga",
                usuario="SISTEMA YUNGA",
            )
            role = "TAPIR - Gestor de documentos y expedientes digitales"
            with stage_scope("pdf.close", "Cerrar PDF"):
                pdf_b64_filled = close_pdf(pdf_b64, fields_to_fill)
            document_context = self._build_document_context(pdf_b64_filled, execution)
            with stage_scope("certificate.local_load", "Obtener certificado local"):
                certificates = get_certificate_from_local()
            with stage_scope("pdf.sign.local", "Firmar PDF local"):
                signed_pdf_base64 = self.create_and_sign(
                    pdf_b64_filled,
                    certificates,
                    field_id,
                    role,
                    custom_image,
                    document_context,
                )
            return id_doc, error, signed_pdf_base64
        except Exception as exc:
            raise signature_exc.SignatureValidationError(f"Error al firmar documento: {str(exc)}") from exc

    def init_signature_pdf(self, pdf, certificates, batch_id=None):
        error = None
        data_to_sign = None

        pdf_b64 = pdf["pdf"]
        field_id = pdf["firma_lugar"]
        name = pdf["firma_nombre"]
        stamp = pdf["firma_sello"]
        area = pdf["firma_area"]
        cuil = pdf["firma_cuil"]
        id_sello = pdf["id_sello"]
        id_oficina = pdf["id_oficina"]
        is_closing = pdf["firma_cierra"]
        closing_place = pdf["firma_lugarcierre"]
        id_doc = pdf["id_doc"]
        is_digital = pdf["firma_digital"]
        id_user = pdf["id_usuario"]
        filepath = pdf["path_file"]
        es_caratula = pdf.get("es_caratula", False)
        is_project = pdf.get("is_project", False)
        entity_lock = None

        try:
            if certificates:
                with stage_scope("certificate.validate", "Validar certificado"):
                    is_valid, cert_error = validate_certificate_expiration(certificates)
                    if not is_valid:
                        raise signature_exc.SignatureValidationError(
                            f"Error de validación de certificado: {cert_error}"
                        )

            timestamp_ms = int(tiempo.time() * 1000)
            datetimesigned = datetime.now().strftime("%d/%m/%Y %H:%M:%S")
            if is_digital:
                try:
                    with stage_scope("signing_context.init", "Crear contexto de firma"):
                        context, context_result = self.signing_context_store.create_or_get_init_context(
                            batch_id=batch_id or self.generate_batch_id([pdf]),
                            id_doc=str(id_doc),
                            id_user=str(id_user),
                            field_id=str(field_id),
                            is_closing=bool(is_closing),
                            is_digital=bool(is_digital),
                            pdf_b64=pdf_b64,
                        )
                    timestamp_ms = int(context["timestamp_ms"])
                    datetimesigned = context["datetimesigned"]
                    logger.info(
                        "signing_context_init",
                        extra={
                            "obs_attrs": {
                                "subject_type": "document",
                                "subject_key": str(id_doc),
                                "context_result": context_result,
                                "batch_id": context.get("batch_id"),
                            }
                        },
                    )
                except SigningContextConflictError as exc:
                    return id_doc, self._error_payload(
                        id_doc=id_doc,
                        message="Error de contexto pendiente: existe una firma en curso para este documento.",
                        details=str(exc),
                    ), data_to_sign
                except SigningContextUnavailableError as exc:
                    return id_doc, self._error_payload(
                        id_doc=id_doc,
                        message=f"Error de infraestructura al guardar contexto de firma: {exc}",
                    ), data_to_sign
            else:
                entity_lock = self._acquire_entity_lock(
                    "document",
                    str(id_doc),
                    "Existe otra firma local en curso para este documento.",
                )

            execution = self.build_execution_context(timestamp_ms, datetimesigned, is_closing)
            document_context = self._build_document_context(pdf_b64, execution)

            if is_digital:
                signature_text = (
                    f"{stamp}\n{execution.datetimesigned}"
                    if is_project
                    else f"{stamp}\n{area}\n{execution.datetimesigned}"
                )
                custom_image = self._build_signature_image(
                    stamp_text=signature_text,
                    encoded_image_data=app_state.encoded_image["data"],
                    mode="cert",
                    usuario=f"{name}",
                    label_signed_by="Firmado digitalmente por",
                )
                role = name + (", CUIL " + cuil if cuil else "") + ", " + stamp + ", " + area
                with stage_scope("pdf.sign.prepare_data_to_sign", "Preparar datos para firma"):
                    data_to_sign_response = get_data_to_sign_token(
                        pdf_b64,
                        certificates,
                        execution.timestamp_ms,
                        field_id,
                        role,
                        custom_image,
                        document_context.page_count,
                    )
                data_to_sign = data_to_sign_response["bytes"]
                return id_doc, error, data_to_sign

            role = name + (", CUIL " + cuil if cuil else "") + ", " + stamp + ", " + area
            signed_pdf_base64 = self.sign_own_pdf(
                pdf_b64,
                False,
                field_id,
                stamp,
                area,
                name,
                document_context,
                role,
            )

            if is_closing:
                if not es_caratula:
                    with stage_scope("pdf.close", "Cerrar PDF"):
                        if not is_project:
                            lastpdf = get_number_and_date_then_close(
                                signed_pdf_base64,
                                id_doc,
                                page_count=document_context.page_count,
                            )
                        else:
                            lastpdf = get_number_and_date_then_close_project(
                                signed_pdf_base64,
                                id_doc,
                                page_count=document_context.page_count,
                            )
                else:
                    lastpdf = signed_pdf_base64

                finalpdf = self.sign_own_pdf(
                    lastpdf,
                    True,
                    closing_place,
                    stamp,
                    area,
                    name,
                    document_context,
                    role,
                )
                is_closed = True
            else:
                finalpdf = signed_pdf_base64
                is_closed = False

            hash_doc = self._hash_signed_pdf(finalpdf)
            unlock_params = {
                "id_doc": id_doc,
                "id_user": id_user,
                "hash_doc": hash_doc,
                "is_closed": is_closed,
                "id_sello": id_sello,
                "id_oficina": id_oficina,
                "tipo_firma": 1,
                "is_signed": 1,
            }
            db_finalize = unlock_pdf_and_close_task_project if is_project else unlock_pdf_and_close_task
            self._persist_signed_pdf(
                finalpdf=finalpdf,
                filepath=filepath,
                hash_doc=hash_doc,
                unlock_params=unlock_params,
                id_doc=id_doc,
                subject_key=str(id_doc),
                db_finalize=db_finalize,
            )
            return id_doc, error, data_to_sign
        except Exception as exc:
            error = self._error_payload(id_doc=id_doc, message=str(exc))
            return id_doc, error, data_to_sign
        finally:
            self._release_entity_lock(entity_lock)

    def end_signature_pdf(self, pdfs, certificates):
        error = None
        lease_token = None

        try:
            if certificates:
                with stage_scope("certificate.validate", "Validar certificado"):
                    is_valid, cert_error = validate_certificate_expiration(certificates)
                    if not is_valid:
                        raise signature_exc.SignatureValidationError(
                            f"Error de validación de certificado: {cert_error}"
                        )

            pdf_b64 = pdfs["pdf"]
            field_id = pdfs["firma_lugar"]
            name = pdfs["firma_nombre"]
            stamp = pdfs["firma_sello"]
            area = pdfs["firma_area"]
            cuil = pdfs["firma_cuil"]
            id_sello = pdfs["id_sello"]
            id_oficina = pdfs["id_oficina"]
            is_closing = pdfs["firma_cierra"]
            closing_place = pdfs["firma_lugarcierre"]
            id_doc = pdfs["id_doc"]
            signature_value = pdfs["signatureValue"]
            id_user = pdfs["id_usuario"]
            filepath = pdfs["path_file"]
            is_project = pdfs.get("is_project", False)

            claim = self._claim_pdf_context(
                pdf_b64=pdf_b64,
                id_doc=id_doc,
                id_user=id_user,
                field_id=field_id,
                is_closing=is_closing,
                is_digital=True,
            )
            if claim.result == "missing":
                return id_doc, self._error_payload(
                    id_doc=id_doc,
                    message="No se encontró contexto de firma pendiente para el documento (expirado o inexistente).",
                )
            if claim.result == "busy":
                return id_doc, self._error_payload(
                    id_doc=id_doc,
                    message="Existe otra finalización de firma en curso para este documento.",
                )
            if claim.result == "mismatch":
                return id_doc, self._error_payload(
                    id_doc=id_doc,
                    message="Contexto de firma inválido para el documento.",
                )
            if claim.result == "finalized":
                return id_doc, self._error_payload(
                    id_doc=id_doc,
                    message="La firma ya fue finalizada previamente para este documento.",
                )

            lease_token = claim.lease_token
            execution = self.build_execution_context(
                int(claim.context["timestamp_ms"]),
                claim.context["datetimesigned"],
                is_closing,
            )
            document_context = self._build_document_context(pdf_b64, execution)
            signature_text = (
                f"{stamp}\n{execution.datetimesigned}"
                if is_project
                else f"{stamp}\n{area}\n{execution.datetimesigned}"
            )
            custom_image = self._build_signature_image(
                stamp_text=signature_text,
                encoded_image_data=app_state.encoded_image["data"],
                mode="token",
                usuario=f"{name}",
                label_signed_by="Firmado digitalmente por",
            )
            role = name + (", CUIL " + cuil if cuil else "") + ", " + stamp + ", " + area

            with stage_scope("pdf.sign.dss", "Firmar PDF en DSS"):
                signed_pdf_response = sign_document_token(
                    pdf_b64,
                    signature_value,
                    certificates,
                    execution.timestamp_ms,
                    field_id,
                    role,
                    custom_image,
                    document_context.page_count,
                )

            if is_closing:
                with stage_scope("pdf.close", "Cerrar PDF"):
                    if not is_project:
                        lastpdf = get_number_and_date_then_close(
                            signed_pdf_response["bytes"],
                            id_doc,
                            page_count=document_context.page_count,
                        )
                    else:
                        lastpdf = get_number_and_date_then_close_project(
                            signed_pdf_response["bytes"],
                            id_doc,
                            page_count=document_context.page_count,
                        )
                finalpdf = self.sign_own_pdf(
                    lastpdf,
                    True,
                    closing_place,
                    stamp,
                    area,
                    name,
                    document_context,
                    role,
                )
                is_closed = True
            else:
                finalpdf = signed_pdf_response["bytes"]
                is_closed = False

            hash_doc = self._hash_signed_pdf(finalpdf)
            unlock_params = {
                "id_doc": id_doc,
                "id_user": id_user,
                "hash_doc": hash_doc,
                "is_closed": is_closed,
                "id_sello": id_sello,
                "id_oficina": id_oficina,
                "tipo_firma": 2,
                "is_signed": 1,
            }
            db_finalize = unlock_pdf_and_close_task_project if is_project else unlock_pdf_and_close_task

            try:
                self._persist_signed_pdf(
                    finalpdf=finalpdf,
                    filepath=filepath,
                    hash_doc=hash_doc,
                    unlock_params=unlock_params,
                    id_doc=id_doc,
                    subject_key=str(id_doc),
                    db_finalize=db_finalize,
                    lease_token=lease_token,
                )
            except RepairRequiredError:
                lease_token = None
                raise
            except Exception as exc:
                self._release_pdf_context_for_retry(id_doc, lease_token, ERROR_PDF_SAVE_FAILED, str(exc))
                lease_token = None
                raise

            self._complete_pdf_context(id_doc, lease_token)
            lease_token = None
            return id_doc, error
        except Exception as exc:
            if error is None:
                error = self._error_payload(
                    id_doc=pdfs.get("id_doc", "unknown") if isinstance(pdfs, dict) else "unknown",
                    message=f"Error al finalizar firma: {str(exc)}",
                )
            if lease_token:
                self._release_pdf_context_for_retry(
                    pdfs.get("id_doc", "unknown"),
                    lease_token,
                    ERROR_PDF_SAVE_FAILED,
                    error["message"],
                )
            return pdfs.get("id_doc", "unknown"), error

    def init_sign_jades(self, index_data, certificates, data_signature):
        id_exp_signed = None
        error = None
        data_to_sign = None
        index_signed = None
        entity_lock = None

        try:
            jsonb64 = index_data["index"]
            index = json.loads(base64.b64decode(jsonb64).decode("utf-8"))
            tramites = index["tramites"]
            name = data_signature["name"]
            stamp = data_signature["stamp"]
            area = data_signature["area"]
            isdigital = data_signature["isdigital"]
            id_user = data_signature.get("id_user")
            tramite = tramites[-1]
            exp_id = f"{index['numero']}/{index['anio']}/{index['codigo']}/{index['letra']}"
            role = name + ", " + stamp + ", " + area

            if isdigital:
                try:
                    with stage_scope("signing_context.init", "Crear contexto de firma"):
                        jades_context, context_result = self.signing_context_store.create_or_get_jades_context(
                            exp_id=exp_id,
                            id_user=id_user,
                            json_b64=jsonb64,
                        )
                    logger.info(
                        "signing_context_init",
                        extra={
                            "obs_attrs": {
                                "subject_type": "expediente",
                                "subject_key": exp_id,
                                "context_result": context_result,
                            }
                        },
                    )
                    current_time_ms = int(jades_context["timestamp_ms"])
                    with stage_scope("jades.prepare_data_to_sign", "Preparar JSON para firma"):
                        data_to_sign_response = get_data_to_sign_tapir_jades(
                            jsonb64,
                            certificates,
                            current_time_ms,
                            role,
                        )
                    data_to_sign = data_to_sign_response["bytes"]
                except SigningContextConflictError as exc:
                    error = self._error_payload(
                        id_exp=exp_id,
                        message="Error de contexto pendiente para el expediente.",
                        details=str(exc),
                    )
            else:
                entity_lock = self._acquire_entity_lock(
                    "expediente",
                    exp_id,
                    "Existe otra firma local en curso para este expediente.",
                )
                signed_json_b64 = self.sign_own_jades(jsonb64, role)
                tramite["firma"] = signed_json_b64
                id_exp_signed = exp_id
                index_signed = index

            return id_exp_signed, error, data_to_sign, index_signed
        except Exception as exc:
            return id_exp_signed, self._error_payload(
                id_exp=id_exp_signed or "unknown",
                message=f"Error inesperado en init_sign_jades: {str(exc)}",
            ), data_to_sign, index_signed
        finally:
            self._release_entity_lock(entity_lock)

    def end_sign_jades(self, index_data, certificates, data_signature):
        id_exp_signed = None
        error = None
        index_signed = None
        lease_token = None

        try:
            jsonb64 = index_data["index"]
            index = json.loads(base64.b64decode(jsonb64).decode("utf-8"))
            tramites = index["tramites"]
            name = data_signature["name"]
            stamp = data_signature["stamp"]
            area = data_signature["area"]
            isdigital = data_signature["isdigital"]
            id_user = data_signature.get("id_user")
            signature = index_data["signature"]
            exp_id = f"{index['numero']}/{index['anio']}/{index['codigo']}/{index['letra']}"
            role = name + ", " + stamp + ", " + area
            tramite = tramites[-1]

            if isdigital:
                claim = self._claim_jades_context(exp_id=exp_id, id_user=id_user, json_b64=jsonb64)
                if claim.result == "missing":
                    return id_exp_signed, self._error_payload(
                        id_exp=exp_id,
                        message="No se encontró contexto de firma JADES pendiente para el expediente (expirado o inexistente).",
                    ), index_signed
                if claim.result == "busy":
                    return id_exp_signed, self._error_payload(
                        id_exp=exp_id,
                        message="Existe otra finalización de firma JADES en curso para este expediente.",
                    ), index_signed
                if claim.result == "mismatch":
                    return id_exp_signed, self._error_payload(
                        id_exp=exp_id,
                        message="Contexto de firma JADES inválido para el expediente.",
                    ), index_signed
                if claim.result == "finalized":
                    return id_exp_signed, self._error_payload(
                        id_exp=exp_id,
                        message="La firma JADES ya fue finalizada previamente.",
                    ), index_signed

                lease_token = claim.lease_token
                current_time_ms = int(claim.context["timestamp_ms"])
                with stage_scope("jades.sign.dss", "Firmar JSON en DSS"):
                    signed_json_response = sign_document_tapir_jades(
                        jsonb64,
                        signature,
                        certificates,
                        current_time_ms,
                        role,
                    )
                tramite["firma"] = signed_json_response["bytes"]
                self._complete_jades_context(exp_id, lease_token)

            id_exp_signed = exp_id
            index_signed = index
            return id_exp_signed, error, index_signed
        except Exception as exc:
            if lease_token:
                self._release_jades_context_for_retry(
                    exp_id,
                    lease_token,
                    ERROR_PDF_SAVE_FAILED,
                    str(exc),
                )
            return id_exp_signed, self._error_payload(
                id_exp=id_exp_signed or "unknown",
                message=f"Error al finalizar firma JADES: {str(exc)}",
            ), index_signed

    def sign_own_pdf(self, pdf, is_yunga_sign, field_to_sign, stamp, area, name, document_context: DocumentProcessingContext, role):
        datetimesigned = self.normalize_datetimesigned(document_context.execution.datetimesigned)
        if not is_yunga_sign:
            custom_image = self._build_signature_image(
                stamp_text=f"{stamp}\n{area}\n{datetimesigned}",
                encoded_image_data=app_state.encoded_image.get("data")
                if isinstance(app_state.encoded_image, dict)
                else app_state.encoded_image,
                mode="cert",
                usuario=f"{name}",
                label_signed_by="Firmado electrónicamente por",
            )
            stage_key = "pdf.sign.local"
        else:
            custom_image = self._build_signature_image(
                stamp_text=f"TRIBUNAL DE CUENTAS TUCUMÁN\n{datetimesigned}",
                encoded_image_data=app_state.encoded_image_yunga.get("data")
                if isinstance(app_state.encoded_image_yunga, dict)
                else app_state.encoded_image_yunga,
                mode="yunga",
                usuario="SISTEMA YUNGA",
            )
            role = "TAPIR - Gestor de documentos y expedientes digitales"
            stage_key = "pdf.sign.local_close"

        with stage_scope("certificate.local_load", "Obtener certificado local"):
            certificates = get_certificate_from_local()
        with stage_scope(stage_key, "Firmar PDF local"):
            return self.create_and_sign(
                pdf,
                certificates,
                field_to_sign,
                role,
                custom_image,
                document_context,
            )

    @staticmethod
    def create_and_sign(pdf, certificates, field_to_sign, role, custom_image, document_context: DocumentProcessingContext):
        try:
            with stage_scope("pdf.sign.local.get_data_to_sign", "Obtener datos para firma local"):
                data_to_sign_response = get_data_to_sign_certificate(
                    pdf,
                    certificates,
                    document_context.execution.timestamp_ms,
                    field_to_sign,
                    role,
                    custom_image,
                    document_context.page_count,
                )
            with stage_scope("pdf.sign.local.private_key_sign", "Firmar datos con clave local"):
                signature_value = get_signature_value_own(data_to_sign_response["bytes"])
            with stage_scope("pdf.sign.local.submit", "Enviar firma local a DSS"):
                signed_pdf_response = sign_document_certificate(
                    pdf,
                    signature_value,
                    certificates,
                    document_context.execution.timestamp_ms,
                    field_to_sign,
                    role,
                    custom_image,
                    document_context.page_count,
                )
            return signed_pdf_response["bytes"]
        except Exception as exc:
            raise signature_exc.SignatureProcessError(f"Error al firmar documento: {str(exc)}") from exc

    def sign_own_jades(self, json_b64, role):
        try:
            current_time_ms = int(tiempo.time() * 1000)
            with stage_scope("certificate.local_load", "Obtener certificado local"):
                certificates = get_certificate_from_local()
            with stage_scope("jades.sign.local", "Firmar JSON localmente"):
                data_to_sign_response = get_data_to_sign_tapir_jades(
                    json_b64,
                    certificates,
                    current_time_ms,
                    role,
                )
                signature_value = get_signature_value_own(data_to_sign_response["bytes"])
                signed_json_response = sign_document_tapir_jades(
                    json_b64,
                    signature_value,
                    certificates,
                    current_time_ms,
                    role,
                )
            return signed_json_response["bytes"]
        except Exception as exc:
            raise signature_exc.SignatureProcessError(f"Error al firmar documento: {str(exc)}") from exc
        except Exception:
            logger.error(
                "signing_context_release_failed",
                exc_info=True,
                extra={
                    "obs_attrs": {
                        "subject_type": "expediente",
                        "subject_key": exp_id,
                        "error_code": ERROR_CTX_RELEASE_FAILED,
                    }
                },
            )
