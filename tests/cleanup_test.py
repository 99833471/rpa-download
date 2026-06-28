"""Testa a limpeza de pastas _MEI* deixadas para trás (PyInstaller onefile).

Valida que purge_stale_runtime_dirs:
- remove uma pasta _MEI* DESTE app (tem o marcador) que não está em uso;
- ignora _MEI* de outro programa PyInstaller (sem o marcador);
- preserva a pasta da instância atual;
- não toca em pastas que não começam com _MEI;
- pula uma pasta "em uso" (arquivo aberto trava o rename, no Windows).

Uso:  python tests/cleanup_test.py
"""

from __future__ import annotations

import os
import sys
import tempfile

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.installer import _OUR_MARKER, purge_stale_runtime_dirs  # noqa: E402

_failures = []


def check(label, cond):
    print(f"  [{'OK ' if cond else 'FALHOU'}] {label}")
    if not cond:
        _failures.append(label)


def _mei(parent, name, ours):
    d = os.path.join(parent, name)
    os.makedirs(d, exist_ok=True)
    if ours:
        marker = os.path.join(d, _OUR_MARKER)
        os.makedirs(os.path.dirname(marker), exist_ok=True)
        with open(marker, "w", encoding="utf-8") as f:
            f.write("// recorder")
    return d


def main():
    print("== Limpeza de _MEI* ==")
    with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as parent:
        ours_stale = _mei(parent, "_MEI11111", ours=True)
        foreign = _mei(parent, "_MEI22222", ours=False)
        current = _mei(parent, "_MEI33333", ours=True)
        normal = os.path.join(parent, "naoMei")
        os.makedirs(normal, exist_ok=True)

        # Uma pasta "nossa" porém EM USO: mantém um arquivo aberto p/ travar o rename.
        in_use = _mei(parent, "_MEI44444", ours=True)
        locked = open(os.path.join(in_use, "lock.bin"), "w")
        try:
            removed = purge_stale_runtime_dirs(parent, current)
        finally:
            locked.close()

        check("removeu a _MEI* nossa e ociosa", not os.path.isdir(ours_stale))
        check("ignorou a _MEI* de outro app", os.path.isdir(foreign))
        check("preservou a pasta da instância atual", os.path.isdir(current))
        check("ignorou pasta que não é _MEI*", os.path.isdir(normal))
        check("pulou a _MEI* em uso (rename travado)", os.path.isdir(in_use))
        check("contagem de removidas = 1", removed == 1)

    print()
    if _failures:
        print(f"RESULTADO: {len(_failures)} falha(s): {_failures}")
        return 1
    print("RESULTADO: limpeza de _MEI - OK")
    return 0


if __name__ == "__main__":
    sys.exit(main())
