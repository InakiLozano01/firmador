import importlib
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch


CLIENT_DIR = Path(__file__).resolve().parents[1]
if str(CLIENT_DIR) not in sys.path:
    sys.path.insert(0, str(CLIENT_DIR))


class FakeNoCard(Exception):
    pass


class FakeConnection:
    def __init__(self, atr=None, connect_error=None):
        self.atr = atr
        self.connect_error = connect_error
        self.disconnected = False

    def connect(self):
        if self.connect_error:
            raise self.connect_error

    def getATR(self):
        return self.atr

    def disconnect(self):
        self.disconnected = True


class FakeReader:
    def __init__(self, name, connection):
        self.name = name
        self.connection = connection

    def createConnection(self):
        return self.connection


class TokenEnumerationTests(unittest.TestCase):
    def test_token_library_path_must_exist_with_native_library_extension(self):
        tokenmg = importlib.import_module("tokenmg")
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            dll = root / "driver.dll"
            text = root / "driver.txt"
            dll.write_bytes(b"dll")
            text.write_text("not a library", encoding="utf-8")

            self.assertTrue(tokenmg.is_token_library_path_usable(str(dll)))
            self.assertFalse(tokenmg.is_token_library_path_usable(str(text)))
            self.assertFalse(
                tokenmg.is_token_library_path_usable(str(root / "missing.dll"))
            )

    def test_empty_reader_does_not_hide_token_in_later_reader(self):
        tokenmg = importlib.import_module("tokenmg")
        empty_connection = FakeConnection(connect_error=FakeNoCard())
        token_connection = FakeConnection(atr=[0x01, 0xAB])
        readers = [
            FakeReader("Empty Reader", empty_connection),
            FakeReader("Token Reader", token_connection),
        ]

        with (
            patch.object(tokenmg, "NoCardException", FakeNoCard),
            patch.object(tokenmg, "list_smartcard_readers_internal", return_value=readers),
        ):
            tokens = tokenmg.list_tokens_internal()

        self.assertEqual(
            [{"reader": "Token Reader", "ATR": [0x01, 0xAB]}],
            tokens,
        )
        self.assertTrue(empty_connection.disconnected)
        self.assertTrue(token_connection.disconnected)

    def test_user_mapping_falls_back_to_bundled_defaults_and_saves_atomically(self):
        tokenmg = importlib.import_module("tokenmg")
        self.assertTrue(
            hasattr(tokenmg, "BUNDLED_TOKEN_LIB_FILE"),
            "token mapping has no read-only bundled fallback",
        )

        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            user_file = root / "user" / "token_lib.json"
            bundled_file = root / "bundle" / "token_lib.json"
            bundled_file.parent.mkdir()
            bundled_file.write_text('{"Reader": "driver.dll"}', encoding="utf-8")

            with (
                patch.object(tokenmg, "TOKEN_LIB_FILE", str(user_file)),
                patch.object(
                    tokenmg,
                    "BUNDLED_TOKEN_LIB_FILE",
                    str(bundled_file),
                ),
            ):
                self.assertEqual(
                    {"Reader": "driver.dll"},
                    tokenmg.load_token_library_mapping(),
                )
                tokenmg.save_token_library_mapping({"ATR": "new-driver.dll"})

            self.assertEqual(
                '{"ATR": "new-driver.dll"}',
                user_file.read_text(encoding="utf-8"),
            )
            self.assertFalse(user_file.with_suffix(".json.tmp").exists())


if __name__ == "__main__":
    unittest.main()
