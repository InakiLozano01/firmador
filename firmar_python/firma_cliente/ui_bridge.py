"""Bridge module that spawns the ui_helper subprocess to run Tk dialogs.

This avoids importing main / Flask in the child process and works on all
platforms because it uses JSON instead of pickle for the payload.
"""

from __future__ import annotations

import json
import subprocess
import sys
from typing import Any
from pathlib import Path


# Decide how to launch the helper.
# • In normal (non-frozen) runs we can simply execute the helper script file.
# • In a PyInstaller-frozen EXE, launching the same EXE again with a script
#   argument would re-execute the bundled main app and start another Flask
#   server.  Instead we use the "-c 'code'" form so the bootloader only runs
#   the snippet that imports and executes ui_helper.

_IS_FROZEN = getattr(sys, "frozen", False)

if _IS_FROZEN:
    # Launch the same executable with a sentinel argument so main.py
    # detects helper mode and delegates execution to ui_helper without
    # starting Flask again.
    _UI_CMD_BASE: list[str] = [sys.executable, "--ui-helper"]
else:
    # Build the command that starts the helper by absolute script path.
    _UI_HELPER_MAIN = Path(__file__).with_name("ui_helper").joinpath("__main__.py")
    _UI_CMD_BASE: list[str] = [sys.executable, str(_UI_HELPER_MAIN)]


def run_ui(func_name: str, *args: Any, timeout: int | None = None) -> Any:  # noqa: D401
    """Run a small Tk-dialog helper in a separate process and return its result.

    Parameters
    ----------
    func_name
        Name of the helper command (e.g., ``select_token_slot``).
    *args
        Positional arguments that will be JSON-serialised and passed to the
        helper process.
    timeout
        Seconds to wait for completion. ``None`` means wait forever.
    Returns
    -------
    The deserialised JSON object printed by the helper, or ``None`` on error.
    """

    payload = json.dumps(args, ensure_ascii=False)

    try:
        proc = subprocess.run(
            _UI_CMD_BASE + [func_name, payload],
            capture_output=True,
            text=True,
            timeout=timeout,
            check=False,
        )
    except Exception as exc:  # pragma: no cover – subprocess creation failed
        print(f"run_ui: failed to spawn helper for {func_name}: {exc}")
        return None

    if proc.returncode != 0:
        # Helper crashed; print its stderr for debugging.
        if proc.stderr:
            print(f"run_ui: ui_helper stderr for {func_name}:\n{proc.stderr}")
        return None

    try:
        return json.loads(proc.stdout.strip()) if proc.stdout else None
    except json.JSONDecodeError:
        print(
            "run_ui: could not decode JSON from ui_helper output "
            f"for {func_name}: {proc.stdout}"
        )
        return None 