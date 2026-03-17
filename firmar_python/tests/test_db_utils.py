import sys
import types
import unittest
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

try:
    import psycopg2  # noqa: F401
except ImportError:
    psycopg2 = types.ModuleType("psycopg2")
    psycopg2.InterfaceError = Exception
    psycopg2.connect = None
    sys.modules["psycopg2"] = psycopg2

try:
    import PyPDF2  # noqa: F401
except ImportError:
    pypdf2 = types.ModuleType("PyPDF2")

    class _DummyPdfReader:
        def __init__(self, *_args, **_kwargs):
            self.pages = [object()]

    pypdf2.PdfReader = _DummyPdfReader
    sys.modules["PyPDF2"] = pypdf2

from app.exceptions.tool_exc import PDFClosingError
from app.utils import db


class FakeCursor:
    def __init__(self, row=None, execute_error=None):
        self.row = row
        self.execute_error = execute_error
        self.executed = []
        self.closed = False

    def execute(self, sql, params):
        self.executed.append((sql, params))
        if self.execute_error:
            raise self.execute_error

    def fetchone(self):
        return self.row

    def close(self):
        self.closed = True


class FakeConnection:
    def __init__(self, row=None, execute_error=None):
        self.cursor_instance = FakeCursor(row=row, execute_error=execute_error)
        self.commit_count = 0
        self.rollback_count = 0
        self.close_count = 0
        self.closed = 0

    def cursor(self):
        return self.cursor_instance

    def commit(self):
        self.commit_count += 1

    def rollback(self):
        self.rollback_count += 1

    def close(self):
        self.close_count += 1
        self.closed = 1


def _protocolized_row():
    return (
        {
            "status": True,
            "numero": "123",
            "fecha": "2026-03-16",
        },
    )


class DBUtilsTests(unittest.TestCase):
    def test_protocolize_opens_independent_connections_per_call(self):
        conn_one = FakeConnection(row=_protocolized_row())
        conn_two = FakeConnection(row=_protocolized_row())

        with patch("app.utils.db.psycopg2.connect", side_effect=[conn_one, conn_two]) as connect_mock:
            with patch("app.utils.db.close_pdf", return_value="closed-pdf"):
                first = db.get_number_and_date_then_close("cGRm", 11, page_count=1)
                second = db.get_number_and_date_then_close("cGRm", 22, page_count=1)

        self.assertEqual(first, "closed-pdf")
        self.assertEqual(second, "closed-pdf")
        self.assertEqual(connect_mock.call_count, 2)
        self.assertEqual(conn_one.commit_count, 1)
        self.assertEqual(conn_two.commit_count, 1)
        self.assertEqual(conn_one.close_count, 1)
        self.assertEqual(conn_two.close_count, 1)

    def test_protocolize_supports_caller_owned_connection_without_commit(self):
        conn = FakeConnection(row=_protocolized_row())

        with patch("app.utils.db.close_pdf", return_value="closed-pdf"):
            result = db.get_number_and_date_then_close(
                "cGRm",
                33,
                page_count=2,
                conn=conn,
                commit=False,
            )

        self.assertEqual(result, "closed-pdf")
        self.assertEqual(conn.commit_count, 0)
        self.assertEqual(conn.rollback_count, 0)
        self.assertEqual(conn.close_count, 0)

    def test_protocolize_rolls_back_when_close_pdf_fails(self):
        conn = FakeConnection(row=_protocolized_row())

        with patch("app.utils.db.psycopg2.connect", return_value=conn):
            with patch("app.utils.db.close_pdf", side_effect=RuntimeError("close failed")):
                with patch("app.utils.db.logger.error"):
                    with self.assertRaises(PDFClosingError):
                        db.get_number_and_date_then_close("cGRm", 44, page_count=1)

        self.assertEqual(conn.commit_count, 0)
        self.assertEqual(conn.rollback_count, 1)
        self.assertEqual(conn.close_count, 1)

    def test_unlock_helper_respects_caller_transaction_and_defaults_is_signed(self):
        conn = FakeConnection()
        params = {
            "id_doc": 10,
            "id_user": 20,
            "hash_doc": "abc123",
            "is_closed": True,
            "id_sello": 30,
            "id_oficina": 40,
            "tipo_firma": 1,
        }

        db.unlock_pdf_and_close_task(params, conn=conn, commit=False)

        self.assertEqual(conn.commit_count, 0)
        self.assertEqual(conn.rollback_count, 0)
        self.assertEqual(conn.close_count, 0)
        sql, sql_params = conn.cursor_instance.executed[0]
        self.assertIn("f_finalizar_proceso_firmado_v2", sql)
        self.assertEqual(sql_params[2], 1)

    def test_project_unlock_helper_supports_caller_owned_connection_without_commit(self):
        conn = FakeConnection()
        params = {
            "id_doc": 10,
            "id_user": 20,
            "hash_doc": "abc123",
            "is_closed": True,
            "id_sello": 30,
            "id_oficina": 40,
            "tipo_firma": 2,
            "is_signed": 0,
        }

        db.unlock_pdf_and_close_task_project(params, conn=conn, commit=False)

        self.assertEqual(conn.commit_count, 0)
        self.assertEqual(conn.rollback_count, 0)
        self.assertEqual(conn.close_count, 0)
        sql, sql_params = conn.cursor_instance.executed[0]
        self.assertIn("f_proyecto_finalizar_proceso_firmado_v2", sql)
        self.assertEqual(sql_params[2], 0)


if __name__ == "__main__":
    unittest.main()
