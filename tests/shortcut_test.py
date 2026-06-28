"""Valida a criação de atalho .lnk (em pasta temporária, sem tocar nas reais) e
a resolução das pastas Documentos / Menu Iniciar.

Uso:  python tests/shortcut_test.py
"""

from __future__ import annotations

import os
import shutil
import subprocess
import sys
import tempfile

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app import shortcuts  # noqa: E402

_failures = []


def check(label, cond):
    print(f"  [{'OK ' if cond else 'FALHOU'}] {label}")
    if not cond:
        _failures.append(label)


def main():
    if os.name != "nt":
        print("Somente Windows — pulado.")
        return 0

    print("== Resolução de pastas ==")
    docs = shortcuts.documents_dir()
    sm = shortcuts.start_menu_programs_dir()
    print("   Documentos:", docs)
    print("   Menu Iniciar:", sm)
    check("encontrou a pasta Documentos", bool(docs) and os.path.isdir(docs))
    check("encontrou a pasta do Menu Iniciar", bool(sm))

    print("== Criação do atalho .lnk (sandbox) ==")
    target = shutil.which("ping") or r"C:\Windows\System32\ping.exe"
    with tempfile.TemporaryDirectory() as d:
        lnk = os.path.join(d, "RPA Download.lnk")
        ok = shortcuts._create_shortcut(lnk, target, os.path.dirname(target))
        check("atalho criado", ok and os.path.isfile(lnk))
        if os.path.isfile(lnk):
            check("atalho não está vazio", os.path.getsize(lnk) > 0)
            # lê o alvo de volta
            ps = ("$ws=New-Object -ComObject WScript.Shell; "
                  f"$ws.CreateShortcut('{lnk}').TargetPath")
            r = subprocess.run(["powershell", "-NoProfile", "-Command", ps],
                               capture_output=True, text=True, timeout=30)
            got = (r.stdout or "").strip()
            check("alvo do atalho confere", os.path.normcase(got) == os.path.normcase(target))

    print()
    if _failures:
        print(f"RESULTADO: {len(_failures)} falha(s): {_failures}")
        return 1
    print("RESULTADO: atalhos - OK")
    return 0


if __name__ == "__main__":
    sys.exit(main())
