"""Acesso a recursos empacotados (ícone), compatível com o modo congelado (.exe)."""

from __future__ import annotations

import os
import sys


def icon_path() -> str:
    """Caminho do ícone do app, em desenvolvimento e dentro do executável."""
    candidates = [os.path.join(os.path.dirname(os.path.abspath(__file__)), "assets", "icon.ico")]
    base = getattr(sys, "_MEIPASS", None)
    if base:
        candidates.append(os.path.join(base, "app", "assets", "icon.ico"))
        candidates.append(os.path.join(base, "icon.ico"))
    for path in candidates:
        if os.path.isfile(path):
            return path
    return candidates[0]
