"""Entry-point for small Tkinter dialogs.

Run with:  python -m ui_helper <command> <json-payload>
Prints result as JSON to stdout.
"""

# Ensure parent directory (firmar_python/firma_cliente) is on sys.path so that
# 'interfaz' and other sibling modules can be imported when this script is
# executed via an absolute path rather than with `-m ui_helper`.
import json
import sys
from pathlib import Path

# Add parent directory to sys.path if not already present
PARENT_DIR = Path(__file__).resolve().parent.parent
if str(PARENT_DIR) not in sys.path:
    sys.path.insert(0, str(PARENT_DIR))

from interfaz import (
    select_token_slot,
    select_certificate,
    select_library_file,
    get_pin_from_user,
)


def _print(obj):
    print(json.dumps(obj, ensure_ascii=False))


def main() -> None:
    if len(sys.argv) < 2:
        _print(None)
        return

    cmd = sys.argv[1]
    raw_payload = sys.argv[2] if len(sys.argv) > 2 else "null"
    try:
        payload = json.loads(raw_payload)
    except json.JSONDecodeError:
        payload = None

    # Commands
    if cmd == "select_token_slot":
        token_info_list, mode = payload
        container: list[int] = []
        select_token_slot(token_info_list, container, mode)
        _print(container[0] if container else None)

    elif cmd == "select_certificate":
        cert_strings, mode = payload
        container: list[int] = []
        select_certificate(cert_strings, container, mode)
        _print(container[0] if container else None)

    elif cmd == "select_library_file":
        _print(select_library_file())

    elif cmd == "get_pin_from_user":
        (mode,) = payload
        _print(get_pin_from_user(mode))

    else:
        _print(None)


if __name__ == "__main__":
    main() 