"""Carga variables de entorno desde .env junto al ejecutable (o junto a los fuentes en desarrollo)."""

from __future__ import annotations

import sys
from pathlib import Path

_loaded = False


def load_client_dotenv() -> None:
    """Lee el primer .env encontrado; no sobrescribe variables ya definidas en el sistema."""
    global _loaded
    if _loaded:
        return
    _loaded = True
    try:
        from dotenv import load_dotenv
    except ImportError:
        return

    candidates: list[Path] = []
    if getattr(sys, "frozen", False):
        candidates.append(Path(sys.executable).resolve().parent / ".env")
        meipass = getattr(sys, "_MEIPASS", None)
        if meipass:
            candidates.append(Path(meipass) / ".env")
    else:
        candidates.append(Path(__file__).resolve().parent / ".env")

    for path in candidates:
        if path.is_file():
            load_dotenv(path, override=False)
            return
