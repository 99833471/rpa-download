"""Valida que o rótulo do robô dimensiona a célula para caber o nome completo
(nome longo -> célula mais alta). Offscreen.

Uso:  python tests/ui_sizing_test.py
"""

from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from app.models import Robot  # noqa: E402

_failures = []


def check(label, cond):
    print(f"  [{'OK ' if cond else 'FALHOU'}] {label}")
    if not cond:
        _failures.append(label)


def _robot(name):
    return Robot(id=1, block_id=1, name=name, description="", position=0,
                 folder_name=name, size="large", manifest_path="")


def main():
    from PySide6.QtWidgets import QApplication

    from app.ui.widgets.robot_list import RobotList

    QApplication.instance() or QApplication(sys.argv)

    print("== Dimensionamento do rótulo do robô ==")
    short = RobotList(1, "dark")
    short.add_robot(_robot("Custos"))
    h_short = short.item(0).sizeHint().height()

    long = RobotList(2, "dark")
    long.add_robot(_robot("WMS - Gerenciador Workstation Conferentes Relatório Mensal"))
    h_long = long.item(0).sizeHint().height()

    check("célula tem altura > 0", h_short > 0)
    check("nome longo gera célula mais alta", h_long > h_short)
    check("tooltip contém o nome completo",
          "Conferentes" in long.item(0).toolTip())

    print()
    if _failures:
        print(f"RESULTADO: {len(_failures)} falha(s): {_failures}")
        return 1
    print("RESULTADO: dimensionamento do rótulo - OK")
    return 0


if __name__ == "__main__":
    sys.exit(main())
