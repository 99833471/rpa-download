"""Testa o diálogo de revisão (offscreen): montagem do RobotManifest a partir de
uma gravação simulada, incluindo tipo de campo Fórmula e questionário de limites.

Uso:  python tests/review_test.py
"""

from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from app.robot_manifest import DT_DATE, FIELD_FORMULA, FIELD_MANUAL  # noqa: E402

_failures = []


def check(label, cond):
    print(f"  [{'OK ' if cond else 'FALHOU'}] {label}")
    if not cond:
        _failures.append(label)


def main():
    from PySide6.QtWidgets import QApplication

    from app.ui.recording_review import RecordingReviewDialog

    app = QApplication.instance() or QApplication(sys.argv)

    summary = {
        "start_url": "https://exemplo.com",
        "has_login": True,
        "steps": [
            {"action": "goto", "url": "https://exemplo.com", "selectors": []},
            {"action": "fill", "value": "01/06/2026", "tag": "input", "label": "Data inicial",
             "selectors": [{"type": "id", "value": "#data"}, {"type": "xpath", "value": "//input"}]},
            {"action": "click", "tag": "button", "label": "Baixar",
             "selectors": [{"type": "id", "value": "#baixar"}]},
            {"action": "download", "value": "rel.csv", "selectors": []},
        ],
    }

    print("== Diálogo de revisão ==")
    dlg = RecordingReviewDialog(summary, "Robô Custos")

    # Define o campo de data como Fórmula.
    row = dlg._rows[1]
    combo, edit = row["mode"], row["value"]
    check("linha do fill tem combo de tipo", combo is not None)
    # Seleciona "Fórmula" pelo data.
    for i in range(combo.count()):
        if combo.itemData(i) == FIELD_FORMULA:
            combo.setCurrentIndex(i)
            break
    edit.setText("WORKDAY(TODAY(); -1)")

    # Ativa o questionário de limites.
    dlg.limit_check.setChecked(True)
    dlg.max_rows.setValue(500)
    # start_step combo: escolhe o passo #1 (a data).
    for i in range(dlg.start_step.count()):
        if dlg.start_step.itemData(i) == 1:
            dlg.start_step.setCurrentIndex(i)
            break

    manifest = dlg.build_manifest("Robô Custos")

    check("manifesto tem 4 passos", len(manifest.steps) == 4)
    fill = manifest.steps[1]
    check("passo de fill virou tipo fórmula", fill.field is not None and fill.field.type == FIELD_FORMULA)
    check("fórmula preservada", fill.field.formula == "WORKDAY(TODAY(); -1)")
    check("fill manteve 2 seletores", len(fill.selectors) == 2)
    check("limite habilitado", manifest.site_limit.enabled is True)
    check("máximo de linhas = 500", manifest.site_limit.max_rows == 500)
    check("passo da data inicial = 1", manifest.site_limit.start_date_step == 1)
    check("has_login propagado", manifest.has_login is True)
    check("session_file definido", manifest.session_file == "session.bin")

    # Item 3: campo Manual com tipo de dado (data) e nome.
    for i in range(combo.count()):
        if combo.itemData(i) == FIELD_MANUAL:
            combo.setCurrentIndex(i)
            break
    edit.setText("Data inicial")
    row["cfg"] = {"name": "Data inicial", "data_type": DT_DATE, "fmt": "dd/mm/yyyy", "options": []}
    m2 = dlg.build_manifest("Robô Custos")
    f2 = m2.steps[1].field
    check("campo manual com tipo de dado 'data'",
          f2.type == FIELD_MANUAL and f2.data_type == DT_DATE)
    check("nome do campo manual preservado", f2.name == "Data inicial")

    # Clique pode ser marcado como opcional (pop-up) e tem nome.
    crow = dlg._rows[2]  # o clique "Baixar"
    check("linha de clique configurável", crow is not None and crow["action"] == "click")
    for i in range(crow["mode"].count()):
        if crow["mode"].itemData(i) is True:  # "Clicar se aparecer (opcional)"
            crow["mode"].setCurrentIndex(i)
            break
    m3 = dlg.build_manifest("Robô Custos")
    check("clique marcado como opcional (pop-up)", m3.steps[2].optional is True)
    check("passo de clique tem nome sugerido", bool(m3.steps[2].name))

    print()
    if _failures:
        print(f"RESULTADO: {len(_failures)} falha(s): {_failures}")
        return 1
    print("RESULTADO: diálogo de revisão - OK")
    return 0


if __name__ == "__main__":
    sys.exit(main())
