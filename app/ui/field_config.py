"""Configuração de um campo Manual: nome amigável, tipo de dado, formato/opções.

Usado na revisão/redefinição quando um campo é marcado como "Manual (pergunta ao
rodar)". O tipo escolhido define o widget que aparece no preenchimento.
"""

from __future__ import annotations

from PySide6.QtWidgets import (
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QLabel,
    QLineEdit,
    QPlainTextEdit,
)

from ..robot_manifest import (
    DT_BOOL, DT_CHOICE, DT_DATE, DT_DATETIME, DT_DECIMAL, DT_INT, DT_TEXT,
)

DATA_TYPE_ITEMS = [
    ("Texto", DT_TEXT),
    ("Número inteiro", DT_INT),
    ("Número decimal", DT_DECIMAL),
    ("Data", DT_DATE),
    ("Data e hora", DT_DATETIME),
    ("Sim/Não", DT_BOOL),
    ("Lista de opções", DT_CHOICE),
]
_LABEL_BY_TYPE = {v: k for k, v in DATA_TYPE_ITEMS}


def data_type_label(dt: str) -> str:
    return _LABEL_BY_TYPE.get(dt, "Texto")


class FieldConfigDialog(QDialog):
    def __init__(self, current: dict, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Configurar campo")
        self.resize(420, 300)
        form = QFormLayout(self)

        self.name = QLineEdit(current.get("name", ""))
        self.name.setPlaceholderText("Ex.: Data inicial")
        form.addRow("Nome do campo:", self.name)

        self.type = QComboBox()
        for label, value in DATA_TYPE_ITEMS:
            self.type.addItem(label, value)
        idx = self.type.findData(current.get("data_type", DT_TEXT))
        if idx >= 0:
            self.type.setCurrentIndex(idx)
        form.addRow("Tipo de dado:", self.type)

        self.fmt = QLineEdit(current.get("fmt", "dd/mm/yyyy"))
        self.fmt_label = QLabel("Formato da data:")
        form.addRow(self.fmt_label, self.fmt)

        self.options = QPlainTextEdit("\n".join(current.get("options", []) or []))
        self.options.setPlaceholderText("Uma opção por linha")
        self.options_label = QLabel("Opções da lista:")
        form.addRow(self.options_label, self.options)

        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        form.addRow(buttons)

        self.type.currentIndexChanged.connect(self._update_visibility)
        self._update_visibility()

    def _update_visibility(self):
        dt = self.type.currentData()
        is_date = dt in (DT_DATE, DT_DATETIME)
        is_choice = dt == DT_CHOICE
        self.fmt_label.setVisible(is_date)
        self.fmt.setVisible(is_date)
        if is_date and not self.fmt.text().strip():
            self.fmt.setText("dd/mm/yyyy hh:nn" if dt == DT_DATETIME else "dd/mm/yyyy")
        self.options_label.setVisible(is_choice)
        self.options.setVisible(is_choice)

    def result_config(self) -> dict:
        opts = [ln.strip() for ln in self.options.toPlainText().splitlines() if ln.strip()]
        return {
            "name": self.name.text().strip(),
            "data_type": self.type.currentData(),
            "fmt": self.fmt.text().strip() or "dd/mm/yyyy",
            "options": opts,
        }
