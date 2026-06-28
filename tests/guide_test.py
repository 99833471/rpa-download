"""Testa a tela de Guia: o GUIA.md existe, carrega e renderiza na janela.

Uso:  python tests/guide_test.py
"""

from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from app.resources import guide_path  # noqa: E402
from app.ui.guide import GuideDialog, load_guide_markdown  # noqa: E402

_failures = []


def check(label, cond):
    print(f"  [{'OK ' if cond else 'FALHOU'}] {label}")
    if not cond:
        _failures.append(label)


def main():
    print("== Tela de Guia ==")
    path = guide_path()
    check("GUIA.md é encontrado", bool(path) and os.path.isfile(path))

    md = load_guide_markdown()
    check("guia carrega conteúdo", len(md) > 200)
    check("guia tem o título esperado", "Guia do RPA Download" in md)
    check("guia menciona ações-chave", ("Aprender" in md or "gravar" in md.lower()) and "Atualizar" in md)

    from PySide6.QtWidgets import QApplication
    app = QApplication.instance() or QApplication(sys.argv)
    dlg = GuideDialog()
    rendered = dlg.view.toPlainText()
    check("a janela renderizou o texto do guia", len(rendered) > 200)
    dlg.close()

    print()
    if _failures:
        print(f"RESULTADO: {len(_failures)} falha(s): {_failures}")
        return 1
    print("RESULTADO: tela de guia - OK")
    return 0


if __name__ == "__main__":
    sys.exit(main())
