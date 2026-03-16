import base64
import hashlib
import json
import logging
import os
import time
from dataclasses import asdict, dataclass
from typing import Dict, List, Optional

from app.config.settings import settings
from ..exceptions.tool_exc import JSONSaveError, PDFSaveError

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class StagedFileWriteResult:
    operation_id: str
    temp_path: str
    target_path: str
    bytes_written: int
    payload_sha256: str


def _ensure_parent_dir(path: str) -> None:
    dirpath = os.path.dirname(path)
    if dirpath:
        os.makedirs(dirpath, exist_ok=True)


def _stage_bytes(data: bytes, target_path: str, operation_id: str) -> StagedFileWriteResult:
    _ensure_parent_dir(target_path)
    temp_path = f"{target_path}.tmp.{operation_id}"
    flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL

    try:
        fd = os.open(temp_path, flags, 0o600)
    except FileExistsError:
        os.remove(temp_path)
        fd = os.open(temp_path, flags, 0o600)

    try:
        with os.fdopen(fd, "wb") as handle:
            handle.write(data)
            handle.flush()
            os.fsync(handle.fileno())
    except Exception:
        try:
            os.remove(temp_path)
        except OSError:
            pass
        raise

    return StagedFileWriteResult(
        operation_id=operation_id,
        temp_path=temp_path,
        target_path=target_path,
        bytes_written=len(data),
        payload_sha256=hashlib.sha256(data).hexdigest(),
    )


def promote_staged_file(staged_file: StagedFileWriteResult) -> str:
    _ensure_parent_dir(staged_file.target_path)
    os.replace(staged_file.temp_path, staged_file.target_path)
    return staged_file.target_path


def discard_staged_file(staged_file: StagedFileWriteResult) -> None:
    try:
        os.remove(staged_file.temp_path)
    except FileNotFoundError:
        return


def stage_signed_pdf(signed_pdf_base64: str, filename: str, operation_id: str) -> StagedFileWriteResult:
    try:
        signed_pdf_bytes = base64.b64decode(signed_pdf_base64)
    except base64.binascii.Error as exc:
        raise PDFSaveError(f"Error al decodificar el PDF en base64: {str(exc)}") from exc

    try:
        return _stage_bytes(signed_pdf_bytes, filename, operation_id)
    except OSError as exc:
        raise PDFSaveError(f"Error al escribir archivo temporal: {str(exc)}") from exc


def stage_signed_json(index, filepath: str, operation_id: str) -> StagedFileWriteResult:
    try:
        encoded = json.dumps(index, separators=(",", ":"), ensure_ascii=False).encode("utf-8")
        return _stage_bytes(encoded, filepath, operation_id)
    except Exception as exc:
        raise JSONSaveError(f"Error al guardar el indice firmado: {str(exc)}") from exc


def save_signed_json(index, filepath):
    logger.info("Starting to save signed JSON to %s", filepath)
    staged = stage_signed_json(index, filepath, operation_id=f"legacy-{int(time.time() * 1000)}")
    try:
        promote_staged_file(staged)
        logger.info("Successfully saved signed JSON")
        return True
    except Exception as exc:
        discard_staged_file(staged)
        logger.error("Failed to promote signed JSON: %s", str(exc), exc_info=True)
        raise JSONSaveError(f"Error al guardar el indice firmado: {str(exc)}") from exc


def save_signed_json_atomic(index, filepath: str, operation_id: str) -> StagedFileWriteResult:
    logger.info("Staging signed JSON to %s", filepath)
    return stage_signed_json(index, filepath, operation_id)


def save_signed_pdf(signed_pdf_base64, filename):
    logger.info("Starting to save signed PDF to %s", filename)
    staged = stage_signed_pdf(signed_pdf_base64, filename, operation_id=f"legacy-{int(time.time() * 1000)}")
    try:
        promote_staged_file(staged)
        logger.info("Successfully saved signed PDF")
        return True
    except Exception as exc:
        discard_staged_file(staged)
        logger.error("Failed to promote signed PDF: %s", str(exc), exc_info=True)
        raise PDFSaveError(f"Error al guardar el PDF firmado: {str(exc)}") from exc


def save_signed_pdf_atomic(signed_pdf_base64: str, filename: str, operation_id: str) -> StagedFileWriteResult:
    logger.info("Staging signed PDF to %s", filename)
    return stage_signed_pdf(signed_pdf_base64, filename, operation_id)


def _repair_manifest_path(staged_file: StagedFileWriteResult) -> str:
    safe_name = hashlib.sha256(staged_file.temp_path.encode("utf-8")).hexdigest()
    return os.path.join(settings.SIGNING_REPAIR_DIR, f"{safe_name}.repair.json")


def write_repair_manifest(
    staged_file: StagedFileWriteResult,
    *,
    id_doc: Optional[str],
    hash_doc: str,
    operation_id: str,
    extra: Optional[Dict] = None,
) -> str:
    os.makedirs(settings.SIGNING_REPAIR_DIR, exist_ok=True)
    manifest_path = _repair_manifest_path(staged_file)
    payload = {
        "operation_id": operation_id,
        "id_doc": str(id_doc) if id_doc is not None else None,
        "target_path": staged_file.target_path,
        "temp_path": staged_file.temp_path,
        "hash_doc": hash_doc,
        "payload_sha256": staged_file.payload_sha256,
        "bytes_written": staged_file.bytes_written,
        "timestamp_ms": int(time.time() * 1000),
    }
    if extra:
        payload.update(extra)

    with open(manifest_path, "w", encoding="utf-8") as handle:
        json.dump(payload, handle, ensure_ascii=False, separators=(",", ":"))
        handle.flush()
        os.fsync(handle.fileno())
    try:
        from app.services.observability.recorder import upsert_repair_manifest

        upsert_repair_manifest(
            operation_id=operation_id,
            id_doc=str(id_doc) if id_doc is not None else None,
            manifest_path=manifest_path,
            target_path=staged_file.target_path,
            temp_path=staged_file.temp_path,
            hash_doc=hash_doc,
            payload_sha256=staged_file.payload_sha256,
            bytes_written=staged_file.bytes_written,
            retryable=True,
            db_committed=bool(extra.get("db_committed")) if extra else False,
            attrs=extra,
        )
    except Exception:
        logger.exception("Failed to register repair manifest in observability")
    return manifest_path


def remove_repair_manifest(manifest_path: str) -> None:
    try:
        os.remove(manifest_path)
    except FileNotFoundError:
        return


def recover_pending_repairs() -> List[Dict]:
    os.makedirs(settings.SIGNING_REPAIR_DIR, exist_ok=True)
    recovered = []
    try:
        from app.services.observability.recorder import update_repair_manifest_status
    except Exception:
        update_repair_manifest_status = None

    for entry in os.listdir(settings.SIGNING_REPAIR_DIR):
        if not entry.endswith(".repair.json"):
            continue
        manifest_path = os.path.join(settings.SIGNING_REPAIR_DIR, entry)
        try:
            with open(manifest_path, "r", encoding="utf-8") as handle:
                payload = json.load(handle)
        except Exception as exc:
            logger.error("Failed to parse repair manifest %s: %s", manifest_path, str(exc))
            continue

        temp_path = payload.get("temp_path")
        target_path = payload.get("target_path")
        expected_sha = payload.get("payload_sha256")
        if not temp_path or not target_path or not expected_sha or not os.path.exists(temp_path):
            continue

        try:
            with open(temp_path, "rb") as handle:
                current_sha = hashlib.sha256(handle.read()).hexdigest()
            if current_sha != expected_sha:
                logger.error("Repair manifest hash mismatch for %s", temp_path)
                if update_repair_manifest_status:
                    update_repair_manifest_status(
                        manifest_path,
                        status="failed",
                        last_error="payload hash mismatch during recovery",
                    )
                continue
            _ensure_parent_dir(target_path)
            os.replace(temp_path, target_path)
            remove_repair_manifest(manifest_path)
            if update_repair_manifest_status:
                update_repair_manifest_status(
                    manifest_path,
                    status="recovered",
                    attrs={"recovered_at_startup": True},
                )
            recovered.append(payload)
        except Exception as exc:
            logger.error("Failed to recover staged file %s: %s", temp_path, str(exc))
            if update_repair_manifest_status:
                update_repair_manifest_status(
                    manifest_path,
                    status="failed",
                    last_error=str(exc),
                )
    return recovered


def repair_backlog_size() -> int:
    if not os.path.isdir(settings.SIGNING_REPAIR_DIR):
        return 0
    return len([entry for entry in os.listdir(settings.SIGNING_REPAIR_DIR) if entry.endswith(".repair.json")])
