import base64
import sys
import types
import unittest
from pathlib import Path
from unittest.mock import patch


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

if "psycopg2" not in sys.modules:
    psycopg2_stub = types.ModuleType("psycopg2")
    psycopg2_stub.InterfaceError = Exception
    psycopg2_stub.connect = None
    sys.modules["psycopg2"] = psycopg2_stub

from app.exceptions.tool_exc import PDFClosingError  # noqa: E402
from app.utils import db as db_utils  # noqa: E402


class FakeCursor:
    def __init__(self, result=None):
        self.result = result
        self.executed = []
        self.closed = False

    def execute(self, query, params):
        self.executed.append((query, params))

    def fetchone(self):
        return (self.result,)

    def close(self):
        self.closed = True


class FakeConnection:
    def __init__(self, result=None):
        self.closed = 0
        self.cursor_obj = FakeCursor(result=result)
        self.commits = 0
        self.rollbacks = 0

    def cursor(self):
        return self.cursor_obj

    def commit(self):
        if self.closed != 0:
            raise RuntimeError("commit on closed connection")
        self.commits += 1

    def rollback(self):
        if self.closed == 0:
            self.rollbacks += 1

    def close(self):
        self.closed = 1


class FakePdfReader:
    def __init__(self, _stream):
        self.pages = [object(), object()]


class DbUtilsTests(unittest.TestCase):
    def setUp(self):
        self.protocol_result = {
            "numero": 222,
            "fecha": "2026-03-16",
            "status": True,
            "solo_fecha": 0,
        }
        self.pdf_b64 = base64.b64encode(b"dummy-pdf").decode("ascii")

    @patch("app.utils.db.PyPDF2.PdfReader", new=FakePdfReader)
    def test_get_number_and_date_then_close_uses_independent_connections(self):
        conn1 = FakeConnection(result=self.protocol_result)
        conn2 = FakeConnection(result=self.protocol_result)

        with patch("app.utils.db.psycopg2.connect", side_effect=[conn1, conn2]):
            with patch("app.utils.db.close_pdf", return_value="closed-pdf"):
                first = db_utils.get_number_and_date_then_close(self.pdf_b64, 63879)
                second = db_utils.get_number_and_date_then_close(self.pdf_b64, 63880)

        self.assertEqual(first, "closed-pdf")
        self.assertEqual(second, "closed-pdf")
        self.assertEqual(conn1.commits, 1)
        self.assertEqual(conn2.commits, 1)
        self.assertEqual(conn1.rollbacks, 0)
        self.assertEqual(conn2.rollbacks, 0)
        self.assertEqual(conn1.closed, 1)
        self.assertEqual(conn2.closed, 1)
        self.assertTrue(conn1.cursor_obj.closed)
        self.assertTrue(conn2.cursor_obj.closed)

    @patch("app.utils.db.PyPDF2.PdfReader", new=FakePdfReader)
    def test_get_number_and_date_then_close_skips_commit_with_external_connection(self):
        conn = FakeConnection(result=self.protocol_result)

        with patch("app.utils.db.close_pdf", return_value="closed-pdf"):
            result = db_utils.get_number_and_date_then_close(
                self.pdf_b64,
                63879,
                conn=conn,
                commit=False,
            )

        self.assertEqual(result, "closed-pdf")
        self.assertEqual(conn.commits, 0)
        self.assertEqual(conn.rollbacks, 0)
        self.assertEqual(conn.closed, 0)
        self.assertTrue(conn.cursor_obj.closed)

    @patch("app.utils.db.PyPDF2.PdfReader", new=FakePdfReader)
    def test_get_number_and_date_then_close_rolls_back_when_pdf_close_fails(self):
        conn = FakeConnection(result=self.protocol_result)

        with patch("app.utils.db.psycopg2.connect", return_value=conn):
            with patch("app.utils.db.close_pdf", side_effect=RuntimeError("boom")):
                with self.assertRaises(PDFClosingError):
                    db_utils.get_number_and_date_then_close(self.pdf_b64, 63879)

        self.assertEqual(conn.commits, 0)
        self.assertEqual(conn.rollbacks, 1)
        self.assertEqual(conn.closed, 1)
        self.assertTrue(conn.cursor_obj.closed)

    def test_unlock_pdf_and_close_task_commits_and_closes_its_connection(self):
        conn = FakeConnection()
        params = {
            "id_doc": 63879,
            "id_user": 139,
            "hash_doc": "abc123",
            "is_closed": True,
            "id_sello": "3",
            "id_oficina": "33",
            "tipo_firma": 1,
        }

        with patch("app.utils.db.psycopg2.connect", return_value=conn):
            db_utils.unlock_pdf_and_close_task(params)

        self.assertEqual(conn.commits, 1)
        self.assertEqual(conn.rollbacks, 0)
        self.assertEqual(conn.closed, 1)
        self.assertTrue(conn.cursor_obj.closed)
        self.assertEqual(len(conn.cursor_obj.executed), 1)

    def test_unlock_pdf_and_close_task_skips_commit_with_external_connection(self):
        conn = FakeConnection()
        params = {
            "id_doc": 63879,
            "id_user": 139,
            "hash_doc": "abc123",
            "is_closed": True,
            "id_sello": "3",
            "id_oficina": "33",
            "tipo_firma": 1,
        }

        db_utils.unlock_pdf_and_close_task(params, conn=conn, commit=False)

        self.assertEqual(conn.commits, 0)
        self.assertEqual(conn.rollbacks, 0)
        self.assertEqual(conn.closed, 0)
        self.assertTrue(conn.cursor_obj.closed)
        self.assertEqual(len(conn.cursor_obj.executed), 1)


if __name__ == "__main__":
    unittest.main()
