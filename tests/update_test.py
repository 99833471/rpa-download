"""Testa (offline) a lógica do atualizador: comparação de versões e o .bat de troca.

Uso:  python tests/update_test.py
"""

from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from app import updater  # noqa: E402
from app.ui.update_controller import build_update_script  # noqa: E402

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

    print("== Script de troca do executável (PowerShell) ==")
    exe = r"C:\App\RPA Download.exe"
    new = r"C:\Temp\new.exe"
    self_ps = r"C:\Temp\rpa_update.ps1"
    ps = build_update_script(4242, new, exe, self_ps)
    check("espera por PID (não pelo nome da imagem)", "$procId=4242" in ps and "Get-Process -Id $procId" in ps)
    check("NÃO espera por IMAGENAME (evita confundir instâncias)", "IMAGENAME" not in ps)
    check("copia o novo sobre o atual", "Copy-Item" in ps and "$new" in ps and "$target" in ps)
    check("reabre o app", "Start-Process -FilePath $target" in ps)
    check("autoexclui o script", "Remove-Item -LiteralPath" in ps and "rpa_update.ps1" in ps)
    check("alvo e origem citados (com aspas seguras)", "'C:\\App\\RPA Download.exe'" in ps and "'C:\\Temp\\new.exe'" in ps)

    print()
    if _failures:
        print(f"RESULTADO: {len(_failures)} falha(s): {_failures}")
        return 1
    print("RESULTADO: lógica do atualizador - OK")
    return 0


if __name__ == "__main__":
    sys.exit(main())
