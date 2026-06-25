"""Montagem de comandos de subprocesso compatível com o modo congelado (.exe).

- Em desenvolvimento: roda ``python -m app.<modulo>``.
- No executável (PyInstaller): roda o PRÓPRIO executável com uma flag de despacho
  (ver o despachante em main.py), pois ``-m`` não existe num app congelado.
"""

from __future__ import annotations

import sys

_MODULES = {
    "executor": "app.executor.executor_process",
    "recorder": "app.recorder.recorder_process",
}
_FLAGS = {"executor": "--rpa-exec", "recorder": "--rpa-record"}


def child_command(mode: str, args: list[str]) -> tuple[str, list[str]]:
    """Retorna (programa, argumentos) para lançar o subprocesso ``mode``."""
    if getattr(sys, "frozen", False):
        return sys.executable, [_FLAGS[mode], *args]
    return sys.executable, ["-m", _MODULES[mode], *args]
