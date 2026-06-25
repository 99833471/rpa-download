"""Diálogo de preenchimento dos campos Manual na hora de executar o robô.

Cada campo aparece com o widget adequado ao seu tipo de dado:
- Texto    -> caixa de texto (dica "Digite aqui")
- Inteiro  -> caixa numérica (dica "0")
- Decimal  -> caixa numérica (dica "0")
- Data     -> seletor de calendário
- Data/hora-> seletor de calendário + hora
- Sim/Não  -> lista Sim/Não
- Lista    -> lista de opções predefinidas
"""

from __future__ import annotations

from PySide6.QtCore import QDate, QDateTime, Qt
from PySide6.QtGui import QDoubleValidator, QIntValidator
from PySide6.QtWidgets import (
    QComboBox,
    QDateEdit,
    QDateTimeEdit,
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QLabel,
    QLineEdit,
)

from .. import formula
from ..robot_manifest import (
    DT_BOOL, DT_CHOICE, DT_DATE, DT_DATETIME, DT_DECIMAL, DT_INT,
)


class ManualInputDialog(QDialog):
    """fields: lista de dicts {index, name, data_type, fmt, options}."""

    def __init__(self, fields: list[dict], robot_name: str, parent=None):
        super().__init__(parent)
        self.setWindowTitle(f"Informações para “{robot_name}”")
        self.setMinimumWidth(420)
        self._fields = fields
        self._widgets = {}

        form = QFormLayout(self)
        intro = QLabel("Preencha os campos abaixo para esta execução:")
        intro.setObjectName("AppSubtitle")
        form.addRow(intro)

        for f in fields:
            label = f.get("name") or f.get("prompt") or "Valor"
            w = self._make_widget(f)
            self._widgets[f["index"]] = (w, f)
            form.addRow(label + ":", w)

        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        buttons.button(QDialogButtonBox.Ok).setText("Executar")
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        form.addRow(buttons)

    def _make_widget(self, f):
        dt = f.get("data_type", "text")
        if dt == DT_INT:
            e = QLineEdit()
            e.setValidator(QIntValidator())
            e.setPlaceholderText("0")
            return e
        if dt == DT_DECIMAL:
            e = QLineEdit()
            v = QDoubleValidator()
            v.setNotation(QDoubleValidator.StandardNotation)
            e.setValidator(v)
            e.setPlaceholderText("0")
            return e
        if dt == DT_DATE:
            d = QDateEdit(QDate.currentDate())
            d.setCalendarPopup(True)
            d.setDisplayFormat("dd/MM/yyyy")
            return d
        if dt == DT_DATETIME:
            d = QDateTimeEdit(QDateTime.currentDateTime())
            d.setCalendarPopup(True)
            d.setDisplayFormat("dd/MM/yyyy HH:mm")
            return d
        if dt == DT_BOOL:
            c = QComboBox()
            c.addItems(["Sim", "Não"])
            return c
        if dt == DT_CHOICE:
            c = QComboBox()
            opts = f.get("options") or []
            c.addItems(opts if opts else ["(sem opções)"])
            return c
        e = QLineEdit()
        e.setPlaceholderText("Digite aqui")
        return e

    def values(self) -> dict:
        """Retorna {index: valor_texto} já formatado."""
        out = {}
        for index, (w, f) in self._widgets.items():
            dt = f.get("data_type", "text")
            fmt = f.get("fmt", "dd/mm/yyyy")
            if isinstance(w, QDateEdit) and not isinstance(w, QDateTimeEdit):
                out[index] = formula.format_date(w.date().toPython(), fmt)
            elif isinstance(w, QDateTimeEdit):
                out[index] = w.dateTime().toPython().strftime(formula._fmt_to_strftime(fmt))
            elif isinstance(w, QComboBox):
                out[index] = w.currentText()
            else:  # QLineEdit (texto/inteiro/decimal)
                out[index] = w.text().strip()
        return out
