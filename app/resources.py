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


def guide_path() -> str | None:
    """Caminho do GUIA.md (passo a passo), em desenvolvimento e no executável."""
    repo_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    candidates = [os.path.join(repo_root, "GUIA.md")]
    base = getattr(sys, "_MEIPASS", None)
    if base:
        candidates.append(os.path.join(base, "GUIA.md"))
        candidates.append(os.path.join(base, "app", "GUIA.md"))
    for path in candidates:
        if os.path.isfile(path):
            return path
    return None
