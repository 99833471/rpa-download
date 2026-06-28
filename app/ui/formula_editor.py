"""Editor de fórmula: digitação com autocomplete, PREVIEW do resultado ao vivo e
lista de funções pesquisável (duplo-clique insere o exemplo)."""

from __future__ import annotations

from PySide6.QtWidgets import (
    QDialog,
    QDialogButtonBox,
    QHeaderView,
    QLabel,
    QLineEdit,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
)

from .. import formula
from .formula_help import formula_completer

_OK_STYLE = "color:#1a7f37; font-weight:600;"
_ERR_STYLE = "color:#b3261e;"


class FormulaEditorDialog(QDialog):
    def __init__(self, initial: str = "", fmt: str = "dd/mm/yyyy", parent=None):
        super().__init__(parent)
        self.setWindowTitle("Editor de fórmula")
        self.resize(720, 560)
        self.fmt = fmt or "dd/mm/yyyy"

        root = QVBoxLayout(self)

        root.addWidget(QLabel("Fórmula (calculada a cada execução):"))
        self.edit = QLineEdit(initial)
        self.edit.setPlaceholderText("Ex.: WORKDAY(TODAY(); -1)   |   TODAY()+1   |   ZEROPAD(MONTH(TODAY()); 2)")
        self.edit.setCompleter(formula_completer(self.edit))
        self.edit.textChanged.connect(self._update_preview)
        root.addWidget(self.edit)

        self.preview = QLabel()
        self.preview.setWordWrap(True)
        root.addWidget(self.preview)

        self.search = QLineEdit()
        self.search.setPlaceholderText("🔎  Buscar função (ex.: data, mês, arredondar)…")
        self.search.textChanged.connect(self._filter)
        root.addWidget(self.search)

        self.table = QTableWidget(len(formula.FORMULAS), 3)
        self.table.setHorizontalHeaderLabels(["Função", "O que faz", "Exemplo"])
        self.table.verticalHeader().setVisible(False)
        self.table.setEditTriggers(QTableWidget.NoEditTriggers)
        self.table.setSelectionBehavior(QTableWidget.SelectRows)
        for i, (name, desc, example) in enumerate(formula.FORMULAS):
            self.table.setItem(i, 0, QTableWidgetItem(name))
            self.table.setItem(i, 1, QTableWidgetItem(desc))
            self.table.setItem(i, 2, QTableWidgetItem(example))
        self.table.resizeColumnsToContents()
        self.table.horizontalHeader().setSectionResizeMode(1, QHeaderView.Stretch)
        self.table.cellDoubleClicked.connect(self._insert_example)
        root.addWidget(self.table, 1)

        hint = QLabel("Duplo-clique numa função insere o exemplo na fórmula.")
        hint.setObjectName("AppSubtitle")
        root.addWidget(hint)

        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        buttons.button(QDialogButtonBox.Ok).setText("Usar fórmula")
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        root.addWidget(buttons)

        self._update_preview()

    def _update_preview(self) -> None:
        text = self.edit.text()
        if not text.strip():
            self.preview.setText("Resultado aparece aqui conforme você digita.")
            self.preview.setStyleSheet("")
            return
        ok, val = formula.preview(text, self.fmt)
        if ok:
            self.preview.setText(f"✔  Resultado: {val}")
            self.preview.setStyleSheet(_OK_STYLE)
        else:
            self.preview.setText(f"✗  {val}")
            self.preview.setStyleSheet(_ERR_STYLE)

    def _filter(self, text: str) -> None:
        q = text.strip().lower()
        for i in range(self.table.rowCount()):
            row_text = " ".join(
                (self.table.item(i, c).text() if self.table.item(i, c) else "")
                for c in range(3)
            ).lower()
            self.table.setRowHidden(i, q not in row_text)

    def _insert_example(self, row: int, _col: int) -> None:
        example = formula.FORMULAS[row][2]
        self.edit.insert(example)
        self.edit.setFocus()

    def result(self) -> str:
        return self.edit.text().strip()
