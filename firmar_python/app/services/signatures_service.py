import base64
import hashlib
import io
import json
import logging
import time as tiempo
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Optional
from zoneinfo import ZoneInfo

from PyPDF2 import PdfReader
from cryptography import x509
from cryptography.hazmat.backends import default_backend

from app.config.state import app_state
from app.exceptions import signature_exc
from app.services.dss.close_pdf import close_pdf
from app.services.dss.dss_json import get_data_to_sign_tapir_jades, sign_document_tapir_jades
from app.services.dss.dss_pdf import (
    get_data_to_sign_certificate as _dss_get_data_certificate,
    get_data_to_sign_token as _dss_get_data_token,
    sign_document_certificate as _dss_sign_certificate,
    sign_document_token as _dss_sign_token,
)
from app.services.externo_context import (
    build_externo_fingerprint,
    externo_context_store,
)
from app.services.dss.placement import get_data_to_sign_with_placement, sign_document_with_placement
from app.services.local_certs import get_certificate_from_local, get_signature_value_own
from app.services.observability import ENTRY_ERROR, current_operation, record_entry, stage_scope
from app.services.signing_context_store import (
    EntityLock,
    FinalizeClaimResult,
    SigningContextConflictError,
    SigningContextUnavailableError,
    signing_context_store,
)
from app.utils.pdf_fields import list_pdf_field_names
from app.utils.pdf_trib import find_marcadores_trib
from app.utils.db import (
    get_number_and_date_then_close,
    get_number_and_date_then_close_project,
    open_db_connection,
    unlock_pdf_and_close_task,
    unlock_pdf_and_close_task_project,
)
from app.utils.image_utils import create_sello_image as create_signature_image, create_signature_image_system
from app.utils.saving import discard_staged_file, promote_staged_file, save_signed_pdf_atomic, write_repair_manifest

logger = logging.getLogger(__name__)

ERROR_CTX_RELEASE_FAILED = "CTX_RELEASE_FAILED"
ERROR_PDF_SAVE_FAILED = "PDF_SAVE_FAILED"
ERROR_PDF_REPAIR_REQUIRED = "PDF_REPAIR_REQUIRED"


def _has_signature_placement(origin_x, origin_y, width, height, page) -> bool:
    return any(value is not None for value in (origin_x, origin_y, width, height, page))


def _get_data_to_sign(
    field_fn,
    pdf,
    certificates,
    current_time,
    field_id,
    stamp,
    encoded_image,
    page_count=None,
    origin_x=None,
    origin_y=None,
    width=None,
    height=None,
    page=None,
):
    if not _has_signature_placement(origin_x, origin_y, width, height, page):
        return field_fn(pdf, certificates, current_time, field_id, stamp, encoded_image, page_count)
    return get_data_to_sign_with_placement(
        pdf,
        certificates,
        current_time,
        field_id,
        stamp,
        encoded_image,
        page_count,
        origin_x=origin_x,
        origin_y=origin_y,
        width=width,
        height=height,
        page=page,
    )


def _sign_document(
    field_fn,
    pdf,
    signature_value,
    certificates,
    current_time,
    field_id,
    stamp,
    encoded_image,
    page_count=None,
    origin_x=None,
    origin_y=None,
    width=None,
    height=None,
    page=None,
):
    if not _has_signature_placement(origin_x, origin_y, width, height, page):
        return field_fn(
            pdf,
            signature_value,
            certificates,
            current_time,
            field_id,
            stamp,
            encoded_image,
            page_count,
        )
    return sign_document_with_placement(
        pdf,
        signature_value,
        certificates,
        current_time,
        field_id,
        stamp,
        encoded_image,
        page_count,
        origin_x=origin_x,
        origin_y=origin_y,
        width=width,
        height=height,
        page=page,
    )


def get_data_to_sign_certificate(*args, **kwargs):
    return _get_data_to_sign(_dss_get_data_certificate, *args, **kwargs)


def sign_document_certificate(*args, **kwargs):
    return _sign_document(_dss_sign_certificate, *args, **kwargs)


def get_data_to_sign_token(*args, **kwargs):
    return _get_data_to_sign(_dss_get_data_token, *args, **kwargs)


def sign_document_token(*args, **kwargs):
    return _sign_document(_dss_sign_token, *args, **kwargs)


TUCUMAN_TZ = ZoneInfo("America/Argentina/Tucuman")


def tucuman_clock(timestamp_ms=None):
    if timestamp_ms is None:
        timestamp_ms = int(tiempo.time() * 1000)
    signed_at = datetime.fromtimestamp(timestamp_ms / 1000, tz=TUCUMAN_TZ)
    return int(timestamp_ms), signed_at.strftime("%d/%m/%Y %H:%M:%S")


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


@dataclass(frozen=True)
class ExternoPrepared:
    id_documento: str
    id_firmante: str
    pdf_b64: str
    field_id: str
    ancla: str
    signature_placement: Optional[dict]
    name: str
    stamp: str
    area: str

    @property
    def fingerprint(self) -> str:
        return build_externo_fingerprint(self.id_documento, self.id_firmante, self.ancla, self.pdf_b64)

    @property
    def role(self) -> str:
        return f"{self.name}, {self.stamp}, {self.area}"


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
    def _error_payload(*, id_doc=None, id_exp=None, id_documento=None, message: str, details: Optional[str] = None):
        payload = {"message": message}
        if id_doc is not None:
            payload["idDocFailed"] = id_doc
        if id_exp is not None:
            payload["idExpFailed"] = id_exp
        if id_documento is not None:
            payload["id_documento"] = id_documento
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

    @staticmethod
    def _rollback_db_connection(conn):
        if conn and conn.closed == 0:
            conn.rollback()

    @staticmethod
    def _close_db_connection(conn):
        if conn and conn.closed == 0:
            conn.close()

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
                extra={"subject_key": subject_key, "db_committed": db_committed},
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

    def _persist_signed_pdf_transactional(
        self,
        *,
        finalpdf: str,
        filepath: str,
        unlock_params: dict,
        db_conn,
        db_finalize,
    ):
        try:
            with stage_scope("task.unlock_close", "Desbloquear y cerrar tarea"):
                db_finalize(unlock_params, conn=db_conn, commit=False)
            with stage_scope("pdf.persist.stage", "Persistir PDF en staging"):
                staged_file = save_signed_pdf_atomic(
                    finalpdf,
                    filepath,
                    self._operation_id_fallback(str(unlock_params["id_doc"])),
                )
            with stage_scope("pdf.persist.promote", "Promover PDF firmado"):
                promote_staged_file(staged_file)
            with stage_scope("db.commit", "Confirmar transaccion de firma"):
                db_conn.commit()
        except Exception:
            self._rollback_db_connection(db_conn)
            raise

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
        transaction_conn = None

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
                transaction_conn = open_db_connection()
                if not es_caratula:
                    protocolize_pdf = (
                        get_number_and_date_then_close_project if is_project else get_number_and_date_then_close
                    )
                    with stage_scope("pdf.close", "Cerrar PDF"):
                        lastpdf = protocolize_pdf(
                            signed_pdf_base64,
                            id_doc,
                            page_count=document_context.page_count,
                            conn=transaction_conn,
                            commit=False,
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
            if is_closing:
                self._persist_signed_pdf_transactional(
                    finalpdf=finalpdf,
                    filepath=filepath,
                    unlock_params=unlock_params,
                    db_conn=transaction_conn,
                    db_finalize=db_finalize,
                )
            else:
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
            self._rollback_db_connection(transaction_conn)
            error = self._error_payload(id_doc=id_doc, message=str(exc))
            return id_doc, error, data_to_sign
        finally:
            self._close_db_connection(transaction_conn)
            self._release_entity_lock(entity_lock)

    def _prepare_documento_externo(self, pdf):
        id_documento = pdf.get("id_documento")
        es_op = pdf.get("es_op")
        if es_op is not True and es_op is not False:
            return None, self._error_payload(
                id_documento=id_documento,
                message="Falta es_op.",
            )
        if not pdf.get("id_firmante"):
            return None, self._error_payload(
                id_documento=id_documento,
                message="Falta id_firmante.",
            )

        pdf_b64 = pdf["pdf"]
        signature_placement = None
        if es_op is True:
            if "firma_lugar" in pdf:
                return None, self._error_payload(
                    id_documento=id_documento,
                    message="Una Orden de Pago no admite Campo de Firma (firma_lugar).",
                )
            markers = find_marcadores_trib(pdf_b64)
            if len(markers) == 0:
                return None, self._error_payload(
                    id_documento=id_documento,
                    message="Falta el Marcador TRIB.",
                )
            if len(markers) > 1:
                return None, self._error_payload(
                    id_documento=id_documento,
                    message="Hay más de un Marcador TRIB.",
                )
            marker = markers[0]
            field_id = ""
            ancla = "OP"
            signature_placement = {
                "origin_x": marker.origin_x,
                "origin_y": marker.origin_y,
                "width": marker.width,
                "height": marker.height,
                "page": marker.page,
            }
        else:
            field_id = pdf.get("firma_lugar")
            if not field_id:
                return None, self._error_payload(
                    id_documento=id_documento,
                    message="Falta el Campo de Firma (firma_lugar).",
                )
            field_names = list_pdf_field_names(pdf_b64)
            if field_id not in field_names:
                return None, self._error_payload(
                    id_documento=id_documento,
                    message=f"El Campo de Firma '{field_id}' no existe en el PDF.",
                )
            ancla = field_id

        return ExternoPrepared(
            id_documento=id_documento,
            id_firmante=pdf.get("id_firmante"),
            pdf_b64=pdf_b64,
            field_id=field_id,
            ancla=ancla,
            signature_placement=signature_placement,
            name=pdf["firma_nombre"],
            stamp=pdf["firma_sello"],
            area=pdf["firma_area"],
        ), None

    def _externo_busy_error(self, id_documento):
        return self._error_payload(
            id_documento=id_documento,
            message="Existe otra firma en curso para este documento.",
        )

    def _lock_documento_externo(self, prepared: ExternoPrepared):
        lock_token = externo_context_store.acquire_lock(prepared.fingerprint)
        if lock_token is None:
            return None, self._externo_busy_error(prepared.id_documento)
        return lock_token, None

    def _externo_token_image(self, prepared: ExternoPrepared, execution, *, mode):
        return self._build_signature_image(
            stamp_text=f"{prepared.stamp}\n{prepared.area}\n{execution.datetimesigned}",
            encoded_image_data=app_state.encoded_image.get("data")
            if isinstance(app_state.encoded_image, dict)
            else app_state.encoded_image,
            mode=mode,
            usuario=f"{prepared.name}",
            label_signed_by="Firmado digitalmente por",
        )

    def _externo_dss_kwargs(self, prepared: ExternoPrepared):
        placement = prepared.signature_placement or {}
        return {
            "origin_x": placement.get("origin_x"),
            "origin_y": placement.get("origin_y"),
            "width": placement.get("width"),
            "height": placement.get("height"),
            "page": placement.get("page"),
        }

    def _externo_execution(self, prepared: ExternoPrepared, *, reuse_digital_clock: bool):
        timestamp_ms, datetimesigned = tucuman_clock()
        if reuse_digital_clock:
            context, _result = externo_context_store.create_or_get_digital(
                prepared.fingerprint,
                timestamp_ms,
                datetimesigned,
            )
            timestamp_ms = context["timestamp_ms"]
            datetimesigned = context["datetimesigned"]
        execution = self.build_execution_context(timestamp_ms, datetimesigned, False)
        document_context = self._build_document_context(prepared.pdf_b64, execution)
        return execution, document_context

    def sign_documento_externo_electronico(self, pdf):
        id_documento = pdf.get("id_documento")
        lock_token = None
        prepared = None
        try:
            prepared, error = self._prepare_documento_externo(pdf)
            if error is not None:
                return id_documento, error, None
            lock_token, error = self._lock_documento_externo(prepared)
            if error is not None:
                return id_documento, error, None
            _execution, document_context = self._externo_execution(prepared, reuse_digital_clock=False)
            signed_pdf = self.sign_own_pdf(
                prepared.pdf_b64,
                False,
                prepared.field_id,
                prepared.stamp,
                prepared.area,
                prepared.name,
                document_context,
                prepared.role,
                signature_placement=prepared.signature_placement,
            )
            return id_documento, None, signed_pdf
        except Exception as exc:
            return id_documento, self._error_payload(
                id_documento=id_documento,
                message=str(exc),
            ), None
        finally:
            if prepared is not None:
                externo_context_store.release_lock(prepared.fingerprint, lock_token)

    def init_documento_externo_digital(self, pdf, certificates):
        id_documento = pdf.get("id_documento")
        lock_token = None
        prepared = None
        try:
            prepared, error = self._prepare_documento_externo(pdf)
            if error is not None:
                return id_documento, error, None
            lock_token, error = self._lock_documento_externo(prepared)
            if error is not None:
                return id_documento, error, None
            execution, document_context = self._externo_execution(prepared, reuse_digital_clock=True)
            custom_image = self._externo_token_image(prepared, execution, mode="cert")
            data_to_sign_response = get_data_to_sign_token(
                prepared.pdf_b64,
                certificates,
                execution.timestamp_ms,
                prepared.field_id,
                prepared.role,
                custom_image,
                document_context.page_count,
                **self._externo_dss_kwargs(prepared),
            )
            return id_documento, None, data_to_sign_response["bytes"]
        except Exception as exc:
            return id_documento, self._error_payload(
                id_documento=id_documento,
                message=str(exc),
            ), None
        finally:
            if prepared is not None:
                externo_context_store.release_lock(prepared.fingerprint, lock_token)

    def end_documento_externo_digital(self, pdf, certificates):
        id_documento = pdf.get("id_documento")
        lock_token = None
        prepared = None
        lease_token = None
        try:
            prepared, error = self._prepare_documento_externo(pdf)
            if error is not None:
                return id_documento, error, None
            signature_value = pdf.get("signatureValue")
            if not signature_value:
                return id_documento, self._error_payload(
                    id_documento=id_documento,
                    message="Falta signatureValue.",
                ), None
            lock_token, error = self._lock_documento_externo(prepared)
            if error is not None:
                return id_documento, error, None
            claim = externo_context_store.claim_for_end(prepared.fingerprint)
            claim_errors = {
                "missing": "No se encontró contexto de firma pendiente para el documento.",
                "busy": None,
                "finalized": "La firma ya fue finalizada previamente para este documento.",
            }
            if claim.result != "claimed":
                if claim.result == "busy":
                    return id_documento, self._externo_busy_error(id_documento), None
                message = claim_errors.get(claim.result, "Contexto de firma inválido para el documento.")
                error = self._error_payload(id_documento=id_documento, message=message)
                if claim.result == "finalized":
                    error["finalized"] = True
                return id_documento, error, None

            lease_token = claim.lease_token
            execution = self.build_execution_context(
                claim.context["timestamp_ms"],
                claim.context["datetimesigned"],
                False,
            )
            document_context = self._build_document_context(prepared.pdf_b64, execution)
            custom_image = self._externo_token_image(prepared, execution, mode="token")
            signed_pdf_response = sign_document_token(
                prepared.pdf_b64,
                signature_value,
                certificates,
                execution.timestamp_ms,
                prepared.field_id,
                prepared.role,
                custom_image,
                document_context.page_count,
                **self._externo_dss_kwargs(prepared),
            )
            externo_context_store.complete(prepared.fingerprint, lease_token)
            lease_token = None
            return id_documento, None, signed_pdf_response.get("bytes", "")
        except Exception as exc:
            if prepared is not None and lease_token:
                externo_context_store.release_claim(prepared.fingerprint, lease_token)
            return id_documento, self._error_payload(
                id_documento=id_documento,
                message=str(exc),
            ), None
        finally:
            if prepared is not None:
                externo_context_store.release_lock(prepared.fingerprint, lock_token)

    def end_signature_pdf(self, pdfs, certificates):
        error = None
        lease_token = None
        transaction_conn = None

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
                transaction_conn = open_db_connection()
                protocolize_pdf = (
                    get_number_and_date_then_close_project if is_project else get_number_and_date_then_close
                )
                with stage_scope("pdf.close", "Cerrar PDF"):
                    lastpdf = protocolize_pdf(
                        signed_pdf_response["bytes"],
                        id_doc,
                        page_count=document_context.page_count,
                        conn=transaction_conn,
                        commit=False,
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
                if is_closing:
                    self._persist_signed_pdf_transactional(
                        finalpdf=finalpdf,
                        filepath=filepath,
                        unlock_params=unlock_params,
                        db_conn=transaction_conn,
                        db_finalize=db_finalize,
                    )
                else:
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
            self._rollback_db_connection(transaction_conn)
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
        finally:
            self._close_db_connection(transaction_conn)

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

    def sign_own_pdf(self, pdf, is_yunga_sign, field_to_sign, stamp, area, name, document_context: DocumentProcessingContext, role, signature_placement=None):
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
                signature_placement=signature_placement,
            )

    @staticmethod
    def create_and_sign(pdf, certificates, field_to_sign, role, custom_image, document_context: DocumentProcessingContext, signature_placement=None):
        placement = signature_placement or {}
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
                    origin_x=placement.get("origin_x"),
                    origin_y=placement.get("origin_y"),
                    width=placement.get("width"),
                    height=placement.get("height"),
                    page=placement.get("page"),
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
                    origin_x=placement.get("origin_x"),
                    origin_y=placement.get("origin_y"),
                    width=placement.get("width"),
                    height=placement.get("height"),
                    page=placement.get("page"),
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
