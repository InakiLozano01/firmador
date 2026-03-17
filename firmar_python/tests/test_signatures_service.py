import base64
import importlib
import sys
import types
import unittest
from contextlib import contextmanager
from pathlib import Path
from unittest.mock import MagicMock, patch

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


def _install_service_stubs():
    state_module = types.ModuleType("app.config.state")
    state_module.app_state = types.SimpleNamespace(
        encoded_image={"data": "image"},
        encoded_image_yunga={"data": "image"},
    )
    sys.modules["app.config.state"] = state_module

    close_pdf_module = types.ModuleType("app.services.dss.close_pdf")
    close_pdf_module.close_pdf = lambda pdf, _fields: pdf
    sys.modules["app.services.dss.close_pdf"] = close_pdf_module

    dss_json_module = types.ModuleType("app.services.dss.dss_json")
    dss_json_module.get_data_to_sign_tapir_jades = lambda *args, **kwargs: {"bytes": "jades"}
    dss_json_module.sign_document_tapir_jades = lambda *args, **kwargs: {"bytes": "jades-signed"}
    sys.modules["app.services.dss.dss_json"] = dss_json_module

    dss_pdf_module = types.ModuleType("app.services.dss.dss_pdf")
    dss_pdf_module.get_data_to_sign_certificate = lambda *args, **kwargs: {"bytes": "cert-data"}
    dss_pdf_module.get_data_to_sign_token = lambda *args, **kwargs: {"bytes": "token-data"}
    dss_pdf_module.sign_document_certificate = lambda *args, **kwargs: {"bytes": "cert-signed"}
    dss_pdf_module.sign_document_token = lambda *args, **kwargs: {"bytes": "token-signed"}
    sys.modules["app.services.dss.dss_pdf"] = dss_pdf_module

    local_certs_module = types.ModuleType("app.services.local_certs")
    local_certs_module.get_certificate_from_local = lambda: {"certificate": "cert"}
    local_certs_module.get_signature_value_own = lambda *_args, **_kwargs: "signature"
    sys.modules["app.services.local_certs"] = local_certs_module

    observability_module = types.ModuleType("app.services.observability")
    observability_module.ENTRY_ERROR = "ENTRY_ERROR"
    observability_module.current_operation = lambda: {}
    observability_module.record_entry = lambda **_kwargs: None

    @contextmanager
    def _stage_scope(*_args, **_kwargs):
        yield

    observability_module.stage_scope = _stage_scope
    sys.modules["app.services.observability"] = observability_module

    signing_context_module = types.ModuleType("app.services.signing_context_store")
    signing_context_module.EntityLock = type("EntityLock", (), {})
    signing_context_module.FinalizeClaimResult = type("FinalizeClaimResult", (), {})
    signing_context_module.SigningContextConflictError = type("SigningContextConflictError", (Exception,), {})
    signing_context_module.SigningContextUnavailableError = type("SigningContextUnavailableError", (Exception,), {})
    signing_context_module.signing_context_store = types.SimpleNamespace(
        generate_batch_id=lambda *_args, **_kwargs: "batch",
        build_pdf_sha256=lambda *_args, **_kwargs: "sha256",
        build_request_fingerprint=lambda **_kwargs: "fingerprint",
        build_jades_request_fingerprint=lambda **_kwargs: "fingerprint",
        build_json_sha256=lambda *_args, **_kwargs: "jsonsha",
        acquire_entity_lock=lambda *_args, **_kwargs: object(),
        release_entity_lock=lambda *_args, **_kwargs: True,
    )
    sys.modules["app.services.signing_context_store"] = signing_context_module

    image_utils_module = types.ModuleType("app.utils.image_utils")
    image_utils_module.create_sello_image = lambda *args, **kwargs: {"data": "image"}
    image_utils_module.create_signature_image_system = lambda *args, **kwargs: {"data": "image"}
    sys.modules["app.utils.image_utils"] = image_utils_module

    saving_module = types.ModuleType("app.utils.saving")
    saving_module.discard_staged_file = lambda *_args, **_kwargs: None
    saving_module.promote_staged_file = lambda *_args, **_kwargs: None
    saving_module.save_signed_pdf_atomic = lambda *_args, **_kwargs: types.SimpleNamespace(
        temp_path="temp.pdf",
        target_path="final.pdf",
    )
    saving_module.write_repair_manifest = lambda *_args, **_kwargs: "repair.json"
    sys.modules["app.utils.saving"] = saving_module


_install_service_stubs()
signatures_service = importlib.import_module("app.services.signatures_service")


class FakeConnection:
    def __init__(self, commit_error=None):
        self.commit_error = commit_error
        self.commit_count = 0
        self.rollback_count = 0
        self.close_count = 0
        self.closed = 0

    def commit(self):
        self.commit_count += 1
        if self.commit_error is not None:
            raise self.commit_error

    def rollback(self):
        self.rollback_count += 1

    def close(self):
        self.close_count += 1
        self.closed = 1


class SignaturesServiceTransactionTests(unittest.TestCase):
    def test_init_signature_pdf_uses_one_transaction_for_close_sign(self):
        service = signatures_service.SignaturesService()
        transaction_conn = FakeConnection()
        lock = object()
        staged_file = types.SimpleNamespace(temp_path="temp.pdf", target_path="target.pdf")

        input_pdf = base64.b64encode(b"input-pdf").decode("ascii")
        signed_pdf = base64.b64encode(b"signed-pdf").decode("ascii")
        protocolized_pdf = base64.b64encode(b"protocolized-pdf").decode("ascii")
        final_pdf = base64.b64encode(b"final-pdf").decode("ascii")

        payload = {
            "pdf": input_pdf,
            "firma_lugar": "sig_field",
            "firma_nombre": "User",
            "firma_sello": "Seal",
            "firma_area": "Area",
            "firma_cuil": "20-1",
            "id_sello": 1,
            "id_oficina": 2,
            "firma_cierra": True,
            "firma_lugarcierre": "close_field",
            "id_doc": 100,
            "firma_digital": False,
            "id_usuario": 200,
            "path_file": "Y:/signed.pdf",
            "es_caratula": False,
            "is_project": False,
        }

        with patch.object(service, "_acquire_entity_lock", return_value=lock):
            with patch.object(service, "_build_document_context") as build_context_mock:
                with patch.object(service, "sign_own_pdf", side_effect=[signed_pdf, final_pdf]):
                    with patch("app.services.signatures_service.open_db_connection", return_value=transaction_conn):
                        with patch(
                            "app.services.signatures_service.get_number_and_date_then_close",
                            return_value=protocolized_pdf,
                        ) as protocolize_mock:
                            with patch(
                                "app.services.signatures_service.unlock_pdf_and_close_task",
                                new=MagicMock(),
                            ) as finalize_mock:
                                with patch(
                                    "app.services.signatures_service.save_signed_pdf_atomic",
                                    return_value=staged_file,
                                ) as stage_mock:
                                    with patch("app.services.signatures_service.promote_staged_file") as promote_mock:
                                        build_context_mock.return_value = signatures_service.DocumentProcessingContext(
                                            execution=signatures_service.SigningExecutionContext(
                                                timestamp_ms=1,
                                                datetimesigned="16/03/2026 12:00:00",
                                                is_closing=True,
                                            ),
                                            source_pdf_sha256="sha",
                                            page_count=1,
                                        )
                                        doc_id, error, data_to_sign = service.init_signature_pdf(payload, certificates=None)

        self.assertEqual(doc_id, 100)
        self.assertIsNone(error)
        self.assertIsNone(data_to_sign)
        protocolize_mock.assert_called_once_with(
            signed_pdf,
            100,
            page_count=1,
            conn=transaction_conn,
            commit=False,
        )
        finalize_mock.assert_called_once()
        self.assertEqual(finalize_mock.call_args.kwargs["conn"], transaction_conn)
        self.assertFalse(finalize_mock.call_args.kwargs["commit"])
        stage_mock.assert_called_once_with(final_pdf, "Y:/signed.pdf", unittest.mock.ANY)
        promote_mock.assert_called_once_with(staged_file)
        self.assertEqual(transaction_conn.commit_count, 1)
        self.assertEqual(transaction_conn.rollback_count, 0)
        self.assertEqual(transaction_conn.close_count, 1)

    def test_transactional_persist_rolls_back_after_file_write_failure_without_discarding(self):
        service = signatures_service.SignaturesService()
        transaction_conn = FakeConnection(commit_error=RuntimeError("commit failed"))
        staged_file = types.SimpleNamespace(temp_path="temp.pdf", target_path="target.pdf")
        finalize_mock = MagicMock()

        with patch("app.services.signatures_service.save_signed_pdf_atomic", return_value=staged_file):
            with patch("app.services.signatures_service.promote_staged_file") as promote_mock:
                with patch("app.services.signatures_service.discard_staged_file") as discard_mock:
                    with self.assertRaises(RuntimeError):
                        service._persist_signed_pdf_transactional(
                            finalpdf=base64.b64encode(b"final-pdf").decode("ascii"),
                            filepath="Y:/signed.pdf",
                            unlock_params={"id_doc": 500},
                            db_conn=transaction_conn,
                            db_finalize=finalize_mock,
                        )

        finalize_mock.assert_called_once()
        self.assertEqual(finalize_mock.call_args.kwargs["conn"], transaction_conn)
        self.assertFalse(finalize_mock.call_args.kwargs["commit"])
        promote_mock.assert_called_once_with(staged_file)
        discard_mock.assert_not_called()
        self.assertEqual(transaction_conn.rollback_count, 1)


if __name__ == "__main__":
    unittest.main()
