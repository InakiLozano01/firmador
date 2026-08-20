import importlib
import sys
import unittest
from pathlib import Path


CLIENT_DIR = Path(__file__).resolve().parents[1]
if str(CLIENT_DIR) not in sys.path:
    sys.path.insert(0, str(CLIENT_DIR))


class FakeServer:
    def __init__(self):
        self.serve_count = 0
        self.shutdown_count = 0

    def serve_forever(self):
        self.serve_count += 1

    def shutdown(self):
        self.shutdown_count += 1


class SignerStartupTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.main = importlib.import_module("main")

    def test_server_is_bound_before_background_thread_starts(self):
        calls = []
        server = FakeServer()

        def server_factory(host, port, app, threaded):
            calls.append((host, port, app, threaded))
            return server

        created = self.main.create_flask_server(server_factory=server_factory)

        self.assertIs(server, created)
        self.assertEqual(
            [("127.0.0.1", 5000, self.main.app, True)],
            calls,
        )

    def test_port_binding_failure_becomes_startup_error(self):
        def failing_factory(*_args, **_kwargs):
            raise OSError("address already in use")

        with self.assertRaises(self.main.SignerStartupError):
            self.main.create_flask_server(server_factory=failing_factory)


if __name__ == "__main__":
    unittest.main()
