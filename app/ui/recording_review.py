"""Diálogo de revisão pós-gravação.

Mostra os passos capturados e permite, para cada campo de preenchimento, escolher
o tipo (Fixo / Fórmula / Manual) e o valor/fórmula/rótulo. Também coleta o
questionário de limites do site (máx. de linhas + estratégia + quais passos
definem o intervalo de datas). Ao confirmar, monta o RobotManifest.
"""

from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QMessageBox,
    QSpinBox,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
)

from .. import formula
from ..robot_manifest import (
    FIELD_FIXED, FIELD_FORMULA, FIELD_MANUAL,
    FieldConfig, RobotManifest, Selector, SiteLimit, Step,
)

_ACTION_LABELS = {
    "goto": "Navegar",
    "click": "Clicar",
    "fill": "Preencher",
    "select": "Selecionar",
    "press": "Tecla",
    "download": "Download",
}
_FIELDABLE = {"fill", "select"}
_TYPE_ITEMS = [("Fixo", FIELD_FIXED), ("Fórmula", FIELD_FORMULA), ("Manual (pergunta ao rodar)", FIELD_MANUAL)]


class RecordingReviewDialog(QDialog):
    def __init__(self, summary: dict, robot_name: str, parent=None):
        super().__init__(parent)
        self.summary = summary
        self.raw_steps = summary.get("steps", [])
        self.setWindowTitle(f"Revisar gravação — {robot_name}")
        self.resize(940, 640)

        root = QVBoxLayout(self)

        info = QLabel(
            f"URL inicial: {summary.get('start_url') or '(definida na gravação)'}\n"
            f"Login/sessão capturada: {'sim' if summary.get('has_login') else 'não'}\n"
            f"Passos gravados: {len(self.raw_steps)}"
        )
        info.setObjectName("AppSubtitle")
        root.addWidget(info)

        self.table = QTableWidget(len(self.raw_steps), 5)
        self.table.setHorizontalHeaderLabels(
            ["#", "Ação", "Elemento", "Tipo do campo", "Valor / Fórmula / Pergunta"]
        )
        self.table.verticalHeader().setVisible(False)
        self.table.horizontalHeader().setSectionResizeMode(2, QHeaderView.Stretch)
        self.table.horizontalHeader().setSectionResizeMode(4, QHeaderView.Stretch)
        root.addWidget(self.table, 1)

        self._rows = []  # (type_combo|None, value_edit|None)
        self._fill_choices = [("(nenhum)", -1)]
        self._build_rows()

        root.addWidget(self._build_limits_group())

        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        buttons.button(QDialogButtonBox.Ok).setText("Salvar robô")
        buttons.button(QDialogButtonBox.Cancel).setText("Descartar")
        buttons.accepted.connect(self._on_accept)
        buttons.rejected.connect(self.reject)
        root.addWidget(buttons)

    # ------------------------------------------------------------- montagem
    def _build_rows(self):
        for i, step in enumerate(self.raw_steps):
            action = step.get("action", "")
            self.table.setItem(i, 0, _ro_item(str(i)))
            self.table.setItem(i, 1, _ro_item(_ACTION_LABELS.get(action, action)))
            self.table.setItem(i, 2, _ro_item(step.get("label") or step.get("url") or ""))

            if action in _FIELDABLE:
                combo = QComboBox()
                for label, value in _TYPE_ITEMS:
                    combo.addItem(label, value)
                edit = QLineEdit(step.get("value", ""))
                combo.currentIndexChanged.connect(
                    lambda _idx, c=combo, e=edit, s=step: self._on_type_changed(c, e, s)
                )
                self.table.setCellWidget(i, 3, combo)
                self.table.setCellWidget(i, 4, edit)
                self._rows.append((combo, edit))
                self._fill_choices.append((f"#{i} — {step.get('label') or step.get('value') or action}", i))
            else:
                self.table.setItem(i, 3, _ro_item("—"))
                self.table.setItem(i, 4, _ro_item(step.get("value", "")))
                self._rows.append((None, None))

    def _on_type_changed(self, combo, edit, step):
        kind = combo.currentData()
        if kind == FIELD_FIXED:
            edit.setPlaceholderText("Valor fixo (ex.: 23/06/2026)")
            if not edit.text():
                edit.setText(step.get("value", ""))
        elif kind == FIELD_FORMULA:
            edit.setPlaceholderText("Fórmula (ex.: WORKDAY(TODAY(); -1))")
        else:  # manual
            edit.setPlaceholderText("Texto da pergunta (ex.: Informe a data inicial)")
            if not edit.text():
                edit.setText(step.get("label", "") or "Informe o valor")

    def _build_limits_group(self) -> QGroupBox:
        group = QGroupBox("Limites do site")
        form = QFormLayout(group)

        self.limit_check = QCheckBox("O site limita a quantidade de linhas/resultados por download")
        form.addRow(self.limit_check)

        self.max_rows = QSpinBox()
        self.max_rows.setRange(1, 100_000_000)
        self.max_rows.setValue(500)
        form.addRow("Máximo por download:", self.max_rows)

        self.strategy = QComboBox()
        self.strategy.addItem("Particionar por data (recursivo)", "date_partition")
        self.strategy.addItem("Paginação", "pagination")
        form.addRow("Estratégia adaptativa:", self.strategy)

        self.start_step = QComboBox()
        self.end_step = QComboBox()
        for label, value in self._fill_choices:
            self.start_step.addItem(label, value)
            self.end_step.addItem(label, value)
        form.addRow("Campo da data inicial:", self.start_step)
        form.addRow("Campo da data final:", self.end_step)

        # Habilita/desabilita conforme o checkbox.
        def _toggle(on):
            for w in (self.max_rows, self.strategy, self.start_step, self.end_step):
                w.setEnabled(on)
        _toggle(False)
        self.limit_check.toggled.connect(_toggle)
        return group

    # ---------------------------------------------------------------- saída
    def _on_accept(self):
        # Valida as fórmulas antes de aceitar.
        for i, (combo, edit) in enumerate(self._rows):
            if combo is not None and combo.currentData() == FIELD_FORMULA:
                ok, msg = formula.validate(edit.text())
                if not ok:
                    QMessageBox.warning(
                        self, "Fórmula inválida",
                        f"Passo #{i}: {msg}\n\nCorrija a fórmula antes de salvar.",
                    )
                    return
        self.accept()

    def build_manifest(self, name: str, session_file: str = "session.bin") -> RobotManifest:
        steps = []
        for i, raw in enumerate(self.raw_steps):
            selectors = [Selector(type=s.get("type", "css"), value=s.get("value", ""))
                         for s in raw.get("selectors", [])]
            field = None
            combo, edit = self._rows[i]
            if combo is not None:
                kind = combo.currentData()
                text = edit.text().strip()
                if kind == FIELD_FIXED:
                    field = FieldConfig(type=FIELD_FIXED, value=text)
                elif kind == FIELD_FORMULA:
                    field = FieldConfig(type=FIELD_FORMULA, formula=text)
                else:
                    field = FieldConfig(type=FIELD_MANUAL, prompt=text or "Informe o valor")
            steps.append(Step(
                action=raw.get("action", ""),
                selectors=selectors,
                url=raw.get("url", ""),
                value=raw.get("value", ""),
                tag=raw.get("tag", ""),
                label=raw.get("label", ""),
                field=field,
            ))

        site_limit = SiteLimit(
            enabled=self.limit_check.isChecked(),
            max_rows=self.max_rows.value(),
            strategy=self.strategy.currentData(),
            start_date_step=self.start_step.currentData(),
            end_date_step=self.end_step.currentData(),
        )
        return RobotManifest(
            name=name,
            start_url=self.summary.get("start_url", ""),
            has_login=bool(self.summary.get("has_login")),
            session_file=session_file,
            site_limit=site_limit,
            steps=steps,
        )


def _ro_item(text: str) -> QTableWidgetItem:
    item = QTableWidgetItem(text)
    item.setFlags(Qt.ItemIsEnabled)
    return item
