import importlib
import inspect
import subprocess
import sys
import types
import unittest
from pathlib import Path
from unittest.mock import patch


CLIENT_DIR = Path(__file__).resolve().parents[1]
if str(CLIENT_DIR) not in sys.path:
    sys.path.insert(0, str(CLIENT_DIR))


class UIBridgeTests(unittest.TestCase):
    def test_helper_diagnostics_do_not_corrupt_json_result(self):
        bridge = importlib.import_module("ui_bridge")
        completed = types.SimpleNamespace(
            returncode=0,
            stdout="Warning: optional icon is missing\n0\n",
            stderr="",
        )

        with patch.object(bridge.subprocess, "run", return_value=completed) as run:
            result = bridge.run_ui("select_token_slot", [], "python")

        self.assertEqual(0, result)
        self.assertEqual(
            bridge.DEFAULT_UI_TIMEOUT_SECONDS,
            run.call_args.kwargs["timeout"],
        )

    def test_ui_helper_bootstraps_without_loading_flask_signer(self):
        main_path = CLIENT_DIR / "main.py"
        script = (
            "import runpy, sys; "
            f"sys.path.insert(0, {str(CLIENT_DIR)!r}); "
            f"sys.argv = [{str(main_path)!r}, '--ui-helper']; "
            "\ntry:\n"
            f"    runpy.run_path({str(main_path)!r}, run_name='__main__')\n"
            "except SystemExit:\n"
            "    pass\n"
            "print('FLASK_LOADED=' + str('flask' in sys.modules))"
        )

        completed = subprocess.run(
            [sys.executable, "-c", script],
            capture_output=True,
            text=True,
            timeout=30,
            check=True,
        )

        self.assertIn("FLASK_LOADED=False", completed.stdout)

    def test_certificate_dialog_has_no_artificial_sleep(self):
        interfaz = importlib.import_module("interfaz")
        source = inspect.getsource(interfaz.select_certificate)

        self.assertNotIn("time.sleep(", source)


if __name__ == "__main__":
    unittest.main()
