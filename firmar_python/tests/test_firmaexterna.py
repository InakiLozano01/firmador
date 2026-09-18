import base64
import io
import os
import sys
import types
import unittest
from pathlib import Path
from unittest.mock import patch

from flask import Flask
from PyPDF2 import PdfReader, PdfWriter
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


def pdf_with_trib_markers(markers, pages=1, extra_field=None) -> str:
    buffer = io.BytesIO()
    pdf = canvas.Canvas(buffer, pagesize=(595, 842))
    by_page = {}
    for page_number, x, y, text in markers:
        by_page.setdefault(page_number, []).append((x, y, text))
    for page_number in range(1, pages + 1):
        if extra_field and page_number == 1:
            pdf.acroForm.textfield(name=extra_field, x=10, y=10, width=100, height=40)
        pdf.setFont("Helvetica", 12)
        for x, y, text in by_page.get(page_number, []):
            pdf.drawString(x, y, text)
        pdf.showPage()
    pdf.save()
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


def _op_item(**overrides):
    payload = _item(
        es_op=True,
        pdf=pdf_with_trib_markers(markers=[(2, 100, 500, "@TRIB")], pages=3),
    )
    payload.pop("firma_lugar", None)
    payload.update(overrides)
    if "firma_lugar" not in overrides:
        payload.pop("firma_lugar", None)
    return payload


class _FirmaExternaClient(unittest.TestCase):
    def setUp(self):
        os.environ["FIRMA_EXTERNA_API_KEY"] = API_KEY
        app = Flask(__name__)
        app.json.sort_keys = False
        register_documento_externo_routes(app)
        self.client = app.test_client()
        self.dss_field_ids = []
        self.sello_labels = []
        self.dss_placements = []

    def tearDown(self):
        os.environ.pop("FIRMA_EXTERNA_API_KEY", None)

    def _auth_headers(self):
        return {"X-API-Key": API_KEY}

    def _post_externa(self, body, headers=None):
        return self.client.post("/firmaexterna", json=body, headers=headers if headers is not None else self._auth_headers())


class FirmaExternaElectronicTests(_FirmaExternaClient):

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

        def capture_get_data(pdf, certificates, current_time, field_id, stamp, encoded_image, page_count=None, **_kwargs):
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


class FirmaExternaElectronicOpTests(_FirmaExternaClient):
    def _capture_dss(self, get_data_mock, sign_mock=None, echo_pdf=False):
        self.dss_placements = []

        def capture_get_data(
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
            **_kwargs,
        ):
            self.dss_placements.append({
                "pdf": pdf,
                "fieldId": field_id,
                "originX": origin_x,
                "originY": origin_y,
                "width": width,
                "height": height,
                "page": page if page is not None else page_count,
            })
            return {"bytes": "data-to-sign"}

        get_data_mock.side_effect = capture_get_data
        if sign_mock is not None and echo_pdf:
            sign_mock.side_effect = lambda pdf, *_args, **_kwargs: {"bytes": pdf}

    @patch("app.services.signatures_service.create_signature_image", return_value={"data": "sello-bytes"})
    @patch("app.services.signatures_service.get_certificate_from_local", return_value={"certificate": "local"})
    @patch("app.services.signatures_service.get_signature_value_own", return_value="sig")
    @patch("app.services.signatures_service.sign_document_certificate", return_value={"bytes": "signed-op"})
    @patch("app.services.signatures_service.get_data_to_sign_certificate")
    def test_op_with_one_trib_uses_rectangle_on_marker_page(self, get_data_mock, *_rest):
        self._capture_dss(get_data_mock)
        item = _op_item(
            id_documento="op-1",
            pdf=pdf_with_trib_markers(markers=[(2, 100, 500, "@trib")], pages=3),
        )

        response = self._post_externa({"firma_digital": False, "pdfs": [item]})
        payload = response.get_json()

        self.assertEqual(response.status_code, 200)
        self.assertTrue(payload["status"])
        self.assertEqual(payload["docsSigned"], ["op-1"])
        self.assertEqual(payload["signedPdfs"], ["signed-op"])
        self.assertEqual(len(self.dss_placements), 1)
        placement = self.dss_placements[0]
        self.assertEqual(placement["fieldId"], "")
        self.assertEqual(placement["page"], 2)
        self.assertEqual(placement["width"], 320)
        self.assertEqual(placement["height"], 80)
        self.assertAlmostEqual(placement["originX"], 100, delta=2)
        self.assertAlmostEqual(placement["originY"] + 80, 500, delta=20)

    @patch("app.services.signatures_service.create_signature_image", return_value={"data": "sello-bytes"})
    @patch("app.services.signatures_service.get_certificate_from_local", return_value={"certificate": "local"})
    @patch("app.services.signatures_service.get_signature_value_own", return_value="sig")
    @patch("app.services.signatures_service.sign_document_certificate", return_value={"bytes": "signed"})
    @patch("app.services.signatures_service.get_data_to_sign_certificate")
    def test_zero_or_two_trib_markers_fail_without_campo_fallback(self, get_data_mock, *_rest):
        self._capture_dss(get_data_mock)
        zero = _op_item(
            id_documento="zero",
            pdf=pdf_with_trib_markers(markers=[], pages=1, extra_field="sig_field"),
        )
        two = _op_item(
            id_documento="two",
            pdf=pdf_with_trib_markers(
                markers=[(1, 40, 200, "@TRIB"), (1, 300, 200, "@TRIB")],
                pages=1,
                extra_field="sig_field",
            ),
        )
        good_campo = _item(id_documento="ok")
        good_op = _op_item(id_documento="ok-op")

        response = self._post_externa({"firma_digital": False, "pdfs": [zero, good_campo, two, good_op]})
        payload = response.get_json()

        self.assertEqual(response.status_code, 200)
        self.assertFalse(payload["status"])
        self.assertEqual(payload["docsSigned"], ["ok", "ok-op"])
        self.assertEqual(payload["docsNotSigned"], ["zero", "two"])
        self.assertEqual(
            [err["id_documento"] for err in payload["errors"]],
            ["zero", "two"],
        )
        self.assertEqual([call["fieldId"] for call in self.dss_placements], ["sig_field", ""])

    @patch("app.services.signatures_service.create_signature_image", return_value={"data": "sello-bytes"})
    @patch("app.services.signatures_service.get_certificate_from_local", return_value={"certificate": "local"})
    @patch("app.services.signatures_service.get_signature_value_own", return_value="sig")
    @patch("app.services.signatures_service.sign_document_certificate", return_value={"bytes": "signed"})
    @patch("app.services.signatures_service.get_data_to_sign_certificate")
    def test_op_with_firma_lugar_fails_only_that_item(self, get_data_mock, *_rest):
        self._capture_dss(get_data_mock)
        invalid = _op_item(id_documento="op-field", firma_lugar="sig_field")
        good_op = _op_item(id_documento="ok-op")

        response = self._post_externa({"firma_digital": False, "pdfs": [invalid, good_op]})
        payload = response.get_json()

        self.assertEqual(response.status_code, 200)
        self.assertFalse(payload["status"])
        self.assertEqual(payload["docsSigned"], ["ok-op"])
        self.assertEqual(payload["docsNotSigned"], ["op-field"])
        self.assertEqual(payload["errors"][0]["id_documento"], "op-field")
        self.assertEqual([call["fieldId"] for call in self.dss_placements], [""])

    @patch("app.services.signatures_service.create_signature_image", return_value={"data": "sello-bytes"})
    @patch("app.services.signatures_service.get_certificate_from_local", return_value={"certificate": "local"})
    @patch("app.services.signatures_service.get_signature_value_own", return_value="sig")
    @patch("app.services.signatures_service.sign_document_certificate", return_value={"bytes": "signed"})
    @patch("app.services.signatures_service.get_data_to_sign_certificate")
    def test_op_with_empty_firma_lugar_key_fails_only_that_item(self, get_data_mock, *_rest):
        self._capture_dss(get_data_mock)
        invalid = _op_item(id_documento="op-empty-field", firma_lugar="")
        good_op = _op_item(id_documento="ok-op")

        response = self._post_externa({"firma_digital": False, "pdfs": [invalid, good_op]})
        payload = response.get_json()

        self.assertEqual(response.status_code, 200)
        self.assertFalse(payload["status"])
        self.assertEqual(payload["docsSigned"], ["ok-op"])
        self.assertEqual(payload["docsNotSigned"], ["op-empty-field"])
        self.assertEqual([call["fieldId"] for call in self.dss_placements], [""])

    @patch("app.services.signatures_service.create_signature_image", return_value={"data": "sello-bytes"})
    @patch("app.services.signatures_service.get_certificate_from_local", return_value={"certificate": "local"})
    @patch("app.services.signatures_service.get_signature_value_own", return_value="sig")
    @patch("app.services.signatures_service.sign_document_certificate", return_value={"bytes": "signed"})
    @patch("app.services.signatures_service.get_data_to_sign_certificate")
    def test_non_op_with_trib_uses_campo_de_firma(self, get_data_mock, *_rest):
        self._capture_dss(get_data_mock)
        pdf = pdf_with_trib_markers(
            markers=[(2, 100, 500, "@TRIB")],
            pages=3,
            extra_field="sig_field",
        )
        response = self._post_externa({
            "firma_digital": False,
            "pdfs": [_item(id_documento="not-op", pdf=pdf, es_op=False, firma_lugar="sig_field")],
        })
        payload = response.get_json()

        self.assertEqual(response.status_code, 200)
        self.assertTrue(payload["status"])
        self.assertEqual(payload["docsSigned"], ["not-op"])
        self.assertEqual(self.dss_placements[0]["fieldId"], "sig_field")
        self.assertNotEqual(self.dss_placements[0]["page"], 2)

    @patch("app.services.signatures_service.create_signature_image", return_value={"data": "sello-bytes"})
    @patch("app.services.signatures_service.get_certificate_from_local", return_value={"certificate": "local"})
    @patch("app.services.signatures_service.get_signature_value_own", return_value="sig")
    @patch("app.services.signatures_service.sign_document_certificate")
    @patch("app.services.signatures_service.get_data_to_sign_certificate")
    def test_mixed_lote_keeps_compact_order_and_trib_text(self, get_data_mock, sign_mock, *_rest):
        self._capture_dss(get_data_mock, sign_mock=sign_mock, echo_pdf=True)
        op_pdf = pdf_with_trib_markers(markers=[(1, 80, 400, "@TRIB")], pages=1)
        op = _op_item(id_documento="op-mix", pdf=op_pdf)
        non_op = _item(id_documento="campo-mix")

        response = self._post_externa({"firma_digital": False, "pdfs": [op, non_op]})
        payload = response.get_json()

        self.assertEqual(response.status_code, 200)
        self.assertTrue(payload["status"])
        self.assertEqual(payload["docsSigned"], ["op-mix", "campo-mix"])
        self.assertEqual(len(payload["signedPdfs"]), 2)
        self.assertEqual([call["fieldId"] for call in self.dss_placements], ["", "sig_field"])
        signed_op = base64.b64decode(payload["signedPdfs"][0])
        trib_text = PdfReader(io.BytesIO(signed_op)).pages[0].extract_text() or ""
        self.assertRegex(trib_text, r"@TRIB")


if __name__ == "__main__":
    unittest.main()
