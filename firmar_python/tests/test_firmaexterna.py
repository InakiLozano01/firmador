import base64
import io
import os
import sys
import types
import unittest
from pathlib import Path
from unittest.mock import patch

from flask import Flask
from PyPDF2 import PdfWriter
from reportlab.pdfgen import canvas


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


def _install_missing_dependency(name, **attrs):
    if name in sys.modules:
        return
    try:
        __import__(name)
    except ImportError:
        module = types.ModuleType(name)
        for key, value in attrs.items():
            setattr(module, key, value)
        sys.modules[name] = module


def _install_import_stubs():
    _install_missing_dependency("psycopg2", InterfaceError=Exception, connect=lambda **_kwargs: None)
    libarchive = types.ModuleType("libarchive")
    libarchive.entry = types.SimpleNamespace(ArchiveEntry=object)
    sys.modules["libarchive"] = libarchive
    sys.modules["libarchive.entry"] = types.ModuleType("libarchive.entry")
    sys.modules["libarchive.entry"].ArchiveEntry = object
    _install_missing_dependency("redis")
    if "redis.exceptions" not in sys.modules:
        redis_exc = types.ModuleType("redis.exceptions")
        redis_exc.RedisError = Exception
        sys.modules["redis.exceptions"] = redis_exc
        if "redis" in sys.modules:
            sys.modules["redis"].exceptions = redis_exc
            sys.modules["redis"].Redis = lambda **_kwargs: types.SimpleNamespace()

    state_module = types.ModuleType("app.config.state")
    state_module.app_state = types.SimpleNamespace(
        encoded_image={"data": "image"},
        encoded_image_yunga={"data": "image"},
    )
    sys.modules["app.config.state"] = state_module

    signing_context_module = types.ModuleType("app.services.signing_context_store")
    signing_context_module.EntityLock = type("EntityLock", (), {})
    signing_context_module.FinalizeClaimResult = type("FinalizeClaimResult", (), {})
    signing_context_module.SigningContextConflictError = type(
        "SigningContextConflictError", (Exception,), {}
    )
    signing_context_module.SigningContextUnavailableError = type(
        "SigningContextUnavailableError", (Exception,), {}
    )
    signing_context_module.signing_context_store = types.SimpleNamespace(
        generate_batch_id=lambda *_args, **_kwargs: "batch",
        build_pdf_sha256=lambda *_args, **_kwargs: "sha256",
        build_request_fingerprint=lambda **_kwargs: "fingerprint",
        acquire_entity_lock=lambda *_args, **_kwargs: object(),
        release_entity_lock=lambda *_args, **_kwargs: True,
    )
    sys.modules["app.services.signing_context_store"] = signing_context_module

    from contextlib import contextmanager

    @contextmanager
    def _noop_scope(*_args, **_kwargs):
        yield

    obs = sys.modules.get("app.services.observability")
    if obs is None:
        obs = types.ModuleType("app.services.observability")
        sys.modules["app.services.observability"] = obs
    obs.SUBJECT_ERROR = getattr(obs, "SUBJECT_ERROR", "SUBJECT_ERROR")
    obs.OPERATION_PARTIAL_ERROR = getattr(obs, "OPERATION_PARTIAL_ERROR", "OPERATION_PARTIAL_ERROR")
    obs.subject_scope = getattr(obs, "subject_scope", _noop_scope)
    obs.stage_scope = getattr(obs, "stage_scope", _noop_scope)
    obs.update_operation = getattr(obs, "update_operation", lambda **_kwargs: None)
    obs.observe_http_operation = getattr(
        obs, "observe_http_operation", lambda _key: (lambda fn: fn)
    )
    obs.current_operation = getattr(obs, "current_operation", lambda: {})
    obs.record_entry = getattr(obs, "record_entry", lambda **_kwargs: None)
    obs.ENTRY_ERROR = getattr(obs, "ENTRY_ERROR", "ENTRY_ERROR")
    obs.install_observability_logging = getattr(obs, "install_observability_logging", lambda: None)


_install_import_stubs()

from app.routes.documento_externo import register_documento_externo_routes


API_KEY = "test-externo-key"


def pdf_with_signature_field(field_name="sig_field") -> str:
    buffer = io.BytesIO()
    pdf = canvas.Canvas(buffer, pagesize=(200, 200))
    pdf.acroForm.textfield(name=field_name, x=10, y=10, width=100, height=40)
    pdf.showPage()
    pdf.save()
    return base64.b64encode(buffer.getvalue()).decode("ascii")


def pdf_without_fields() -> str:
    writer = PdfWriter()
    writer.add_blank_page(width=200, height=200)
    buffer = io.BytesIO()
    writer.write(buffer)
    return base64.b64encode(buffer.getvalue()).decode("ascii")


def _item(**overrides):
    payload = {
        "pdf": pdf_with_signature_field(),
        "es_op": False,
        "id_documento": "doc-1",
        "id_firmante": "user-1",
        "firma_nombre": "Ada Lovelace",
        "firma_sello": "Vocal",
        "firma_area": "Tribunal",
        "firma_lugar": "sig_field",
    }
    payload.update(overrides)
    return payload


class FirmaExternaElectronicTests(unittest.TestCase):
    def setUp(self):
        os.environ["FIRMA_EXTERNA_API_KEY"] = API_KEY
        app = Flask(__name__)
        app.json.sort_keys = False
        register_documento_externo_routes(app)
        self.client = app.test_client()
        self.dss_field_ids = []
        self.sello_labels = []

    def tearDown(self):
        os.environ.pop("FIRMA_EXTERNA_API_KEY", None)

    def _auth_headers(self):
        return {"X-API-Key": API_KEY}

    def _post_externa(self, body, headers=None):
        return self.client.post("/firmaexterna", json=body, headers=headers if headers is not None else self._auth_headers())

    def test_rejects_missing_api_key(self):
        response = self.client.post("/firmaexterna", json={"firma_digital": False, "pdfs": []})
        self.assertEqual(response.status_code, 401)
        payload = response.get_json()
        self.assertFalse(payload["status"])

    def test_rejects_wrong_api_key(self):
        response = self._post_externa(
            {"firma_digital": False, "pdfs": []},
            headers={"X-API-Key": "nope"},
        )
        self.assertEqual(response.status_code, 401)

    def test_firmalote_does_not_require_api_key(self):
        routes_source = (ROOT / "app" / "routes" / "routes.py").read_text(encoding="utf-8")
        self.assertNotIn("X-API-Key", routes_source)
        self.assertNotIn("FIRMA_EXTERNA_API_KEY", routes_source)

    def test_empty_pdfs_is_http_400(self):
        response = self._post_externa({"firma_digital": False, "pdfs": []})
        self.assertEqual(response.status_code, 400)

    def test_electronic_lote_with_certificates_is_http_400(self):
        response = self._post_externa(
            {
                "firma_digital": False,
                "certificates": {"certificate": "abc"},
                "pdfs": [_item()],
            }
        )
        self.assertEqual(response.status_code, 400)

    def test_electronic_lote_with_empty_certificates_object_is_http_400(self):
        response = self._post_externa(
            {
                "firma_digital": False,
                "certificates": {},
                "pdfs": [_item()],
            }
        )
        self.assertEqual(response.status_code, 400)

    @patch("app.services.signatures_service.unlock_pdf_and_close_task")
    @patch("app.services.signatures_service.save_signed_pdf_atomic")
    @patch("app.services.signatures_service.get_number_and_date_then_close")
    @patch("app.services.signatures_service.create_signature_image", return_value={"data": "sello-bytes"})
    @patch("app.services.signatures_service.get_certificate_from_local", return_value={"certificate": "local"})
    @patch("app.services.signatures_service.get_signature_value_own", return_value="sig")
    @patch("app.services.signatures_service.sign_document_certificate")
    @patch("app.services.signatures_service.get_data_to_sign_certificate")
    def test_electronic_campo_de_firma_returns_compact_signed_pdfs(
        self,
        get_data_mock,
        sign_mock,
        _sig_value,
        _local_cert,
        sello_mock,
        protocolize_mock,
        save_mock,
        unlock_mock,
    ):
        get_data_mock.return_value = {"bytes": "data-to-sign"}
        sign_mock.return_value = {"bytes": "signed-pdf-bytes"}
        sello_mock.side_effect = lambda *args, **kwargs: self.sello_labels.append(kwargs.get("label_signed_by")) or {
            "data": "sello-bytes"
        }

        def capture_get_data(pdf, certificates, current_time, field_id, stamp, encoded_image, page_count=None):
            self.dss_field_ids.append(field_id)
            return {"bytes": "data-to-sign"}

        get_data_mock.side_effect = capture_get_data

        response = self._post_externa({"firma_digital": False, "pdfs": [_item()]})
        payload = response.get_json()

        self.assertEqual(response.status_code, 200)
        self.assertTrue(payload["status"])
        self.assertEqual(payload["docsSigned"], ["doc-1"])
        self.assertEqual(payload["docsNotSigned"], [])
        self.assertEqual(payload["signedPdfs"], ["signed-pdf-bytes"])
        self.assertEqual(self.dss_field_ids, ["sig_field"])
        self.assertIn("Firmado electrónicamente por", self.sello_labels)
        protocolize_mock.assert_not_called()
        save_mock.assert_not_called()
        unlock_mock.assert_not_called()

    @patch("app.services.signatures_service.create_signature_image", return_value={"data": "sello-bytes"})
    @patch("app.services.signatures_service.get_certificate_from_local", return_value={"certificate": "local"})
    @patch("app.services.signatures_service.get_signature_value_own", return_value="sig")
    @patch("app.services.signatures_service.sign_document_certificate", return_value={"bytes": "signed-b"})
    @patch("app.services.signatures_service.get_data_to_sign_certificate", return_value={"bytes": "data"})
    def test_partial_item_failures_keep_other_signed_pdfs(self, *_mocks):
        good = _item(id_documento="ok")
        missing_field = _item(id_documento="missing-lugar", firma_lugar=None)
        missing_field.pop("firma_lugar")
        absent_field = _item(id_documento="absent-field", pdf=pdf_without_fields(), firma_lugar="sig_field")

        response = self._post_externa(
            {"firma_digital": False, "pdfs": [missing_field, good, absent_field]}
        )
        payload = response.get_json()

        self.assertEqual(response.status_code, 200)
        self.assertFalse(payload["status"])
        self.assertEqual(payload["docsSigned"], ["ok"])
        self.assertEqual(payload["signedPdfs"], ["signed-b"])
        self.assertEqual(payload["docsNotSigned"], ["missing-lugar", "absent-field"])
        error_ids = [err["id_documento"] for err in payload["errors"]]
        self.assertEqual(error_ids, ["missing-lugar", "absent-field"])

    @patch("app.services.signatures_service.create_signature_image", return_value={"data": "sello-bytes"})
    @patch("app.services.signatures_service.get_certificate_from_local", return_value={"certificate": "local"})
    @patch("app.services.signatures_service.get_signature_value_own", return_value="sig")
    @patch("app.services.signatures_service.sign_document_certificate", return_value={"bytes": "signed-c"})
    @patch("app.services.signatures_service.get_data_to_sign_certificate", return_value={"bytes": "data"})
    def test_duplicate_id_documento_fails_extra_items(self, get_data_mock, *_rest):
        first = _item(id_documento="dup")
        second = _item(id_documento="dup")
        response = self._post_externa({"firma_digital": False, "pdfs": [first, second]})
        payload = response.get_json()

        self.assertEqual(response.status_code, 200)
        self.assertFalse(payload["status"])
        self.assertEqual(payload["docsSigned"], ["dup"])
        self.assertEqual(payload["signedPdfs"], ["signed-c"])
        self.assertEqual(payload["docsNotSigned"], ["dup"])
        self.assertEqual(get_data_mock.call_count, 1)

    @patch("app.services.signatures_service.create_signature_image", return_value={"data": "sello-bytes"})
    @patch("app.services.signatures_service.get_certificate_from_local", return_value={"certificate": "local"})
    @patch("app.services.signatures_service.get_signature_value_own", return_value="sig")
    @patch("app.services.signatures_service.sign_document_certificate", return_value={"bytes": ""})
    @patch("app.services.signatures_service.get_data_to_sign_certificate", return_value={"bytes": "data"})
    def test_successful_item_keeps_signed_pdf_slot_even_when_bytes_empty(self, *_mocks):
        response = self._post_externa({"firma_digital": False, "pdfs": [_item()]})
        payload = response.get_json()

        self.assertEqual(response.status_code, 200)
        self.assertEqual(payload["docsSigned"], ["doc-1"])
        self.assertEqual(payload["signedPdfs"], [""])

    def test_missing_es_op_or_id_firmante_fails_only_that_item(self):
        missing_es_op = _item(id_documento="no-es-op")
        missing_es_op.pop("es_op")
        missing_firmante = _item(id_documento="no-firmante")
        missing_firmante.pop("id_firmante")
        good = _item(id_documento="ok")

        with patch("app.services.signatures_service.create_signature_image", return_value={"data": "sello-bytes"}), \
             patch("app.services.signatures_service.get_certificate_from_local", return_value={"certificate": "local"}), \
             patch("app.services.signatures_service.get_signature_value_own", return_value="sig"), \
             patch("app.services.signatures_service.sign_document_certificate", return_value={"bytes": "signed-d"}), \
             patch("app.services.signatures_service.get_data_to_sign_certificate", return_value={"bytes": "data"}):
            response = self._post_externa(
                {"firma_digital": False, "pdfs": [missing_es_op, missing_firmante, good]}
            )
        payload = response.get_json()

        self.assertEqual(response.status_code, 200)
        self.assertFalse(payload["status"])
        self.assertEqual(payload["docsSigned"], ["ok"])
        self.assertEqual(payload["signedPdfs"], ["signed-d"])
        self.assertEqual(payload["docsNotSigned"], ["no-es-op", "no-firmante"])
        self.assertEqual(
            [err["id_documento"] for err in payload["errors"]],
            ["no-es-op", "no-firmante"],
        )


if __name__ == "__main__":
    unittest.main()
