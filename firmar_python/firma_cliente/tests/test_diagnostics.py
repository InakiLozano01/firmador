import importlib
import sys
import tempfile
import unittest
from pathlib import Path


CLIENT_DIR = Path(__file__).resolve().parents[1]
if str(CLIENT_DIR) not in sys.path:
    sys.path.insert(0, str(CLIENT_DIR))


class DiagnosticsTests(unittest.TestCase):
    def test_persistent_log_redacts_sensitive_fields(self):
        try:
            diagnostics = importlib.import_module("diagnostics")
        except ModuleNotFoundError as exc:
            raise AssertionError("diagnostics Module has not been implemented") from exc

        with tempfile.TemporaryDirectory() as directory:
            log_path = diagnostics.configure_diagnostics(
                log_dir=directory,
                force=True,
            )
            diagnostics.log_event(
                "signing_test",
                phase="worker_sign",
                pin="1234",
                data_to_sign=["secret-payload"],
            )
            diagnostics.flush_diagnostics()
            content = Path(log_path).read_text(encoding="utf-8")
            diagnostics.close_diagnostics()

        self.assertIn("signing_test", content)
        self.assertIn("worker_sign", content)
        self.assertNotIn("1234", content)
        self.assertNotIn("secret-payload", content)
        self.assertIn("[REDACTED]", content)


if __name__ == "__main__":
    unittest.main()
