"""Ajuda de fórmulas: diálogo com a lista de fórmulas e um autocomplete."""

from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QCompleter,
    QDialog,
    QDialogButtonBox,
    QHeaderView,
    QLabel,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
)

from .. import formula


def formula_completer(parent=None) -> QCompleter:
    """Autocomplete com os nomes de fórmulas suportadas."""
    comp = QCompleter(formula.FORMULA_NAMES, parent)
    comp.setCaseSensitivity(Qt.CaseInsensitive)
    comp.setFilterMode(Qt.MatchContains)
    comp.setCompletionMode(QCompleter.PopupCompletion)
    return comp


class FormulaHelpDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Fórmulas disponíveis")
        self.resize(720, 460)
        root = QVBoxLayout(self)

        intro = QLabel(
            "Fórmulas dinâmicas (em inglês, separador “;”). O valor é calculado a "
            "cada execução. Exemplos abaixo — clique duas vezes para copiar."
        )
        intro.setObjectName("AppSubtitle")
        intro.setWordWrap(True)
        root.addWidget(intro)

        table = QTableWidget(len(formula.FORMULAS), 3)
        table.setHorizontalHeaderLabels(["Fórmula", "O que faz", "Exemplo"])
        table.verticalHeader().setVisible(False)
        table.horizontalHeader().setSectionResizeMode(1, QHeaderView.Stretch)
        table.setEditTriggers(QTableWidget.NoEditTriggers)
        for i, (name, desc, example) in enumerate(formula.FORMULAS):
            table.setItem(i, 0, QTableWidgetItem(name))
            table.setItem(i, 1, QTableWidgetItem(desc))
            table.setItem(i, 2, QTableWidgetItem(example))
        table.resizeColumnsToContents()
        table.horizontalHeader().setSectionResizeMode(1, QHeaderView.Stretch)
        # Copiar o exemplo ao dar duplo-clique.
        table.cellDoubleClicked.connect(
            lambda r, _c: self._copy(formula.FORMULAS[r][2])
        )
        root.addWidget(table, 1)

        buttons = QDialogButtonBox(QDialogButtonBox.Close)
        buttons.rejected.connect(self.reject)
        buttons.accepted.connect(self.accept)
        root.addWidget(buttons)

    @staticmethod
    def _copy(text: str) -> None:
        from PySide6.QtWidgets import QApplication
        QApplication.clipboard().setText(text)
