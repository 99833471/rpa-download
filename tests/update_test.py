"""Testa (offline) a lógica do atualizador: comparação de versões e o .bat de troca.

Uso:  python tests/update_test.py
"""

from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from app import updater  # noqa: E402
from app.ui.update_controller import build_update_bat  # noqa: E402

_failures = []


def check(label, cond):
    print(f"  [{'OK ' if cond else 'FALHOU'}] {label}")
    if not cond:
        _failures.append(label)


def main():
    print("== Comparação de versões ==")
    check("1.5.2 > 1.5.1", updater.is_newer("v1.5.2", "1.5.1") is True)
    check("igual não atualiza", updater.is_newer("v1.5.2", "1.5.2") is False)
    check("antiga não é newer", updater.is_newer("v1.5.0", "1.5.2") is False)
    check("two-digit minor", updater.is_newer("v1.10.0", "1.9.9") is True)

    print("== .bat de troca do executável ==")
    exe = r"C:\App\RPA Download.exe"
    new = r"C:\Temp\new.exe"
    bat = build_update_bat(exe, new)
    check("usa ping como pausa (robusto sem console)", "ping -n 2 127.0.0.1" in bat)
    check("NÃO usa timeout (depende de console)", "timeout " not in bat)
    check("move o novo sobre o atual", f'move /y "{new}" "{exe}"' in bat)
    check("reabre o app", f'start "" "{exe}"' in bat)
    check("autoexclui o .bat", 'del "%~f0"' in bat)
    check("espera pelo nome do processo", 'IMAGENAME eq RPA Download.exe' in bat)

    print()
    if _failures:
        print(f"RESULTADO: {len(_failures)} falha(s): {_failures}")
        return 1
    print("RESULTADO: lógica do atualizador - OK")
    return 0


if __name__ == "__main__":
    sys.exit(main())
