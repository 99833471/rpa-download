"""Diálogo de revisão pós-gravação (também usado em "Redefinir campos").

Para cada campo de preenchimento permite escolher o tipo (Fixo / Fórmula /
Manual) e o valor/fórmula. Para campos Manual, abre uma configuração de tipo de
dado e nome (⚙). Também coleta o questionário de limites do site. Ao confirmar,
monta o RobotManifest.
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
    QPushButton,
    QSpinBox,
    QTableWidget,
    QTableWidgetItem,
    QToolButton,
    QVBoxLayout,
)

from .. import formula
from ..robot_manifest import (
    DT_TEXT, FIELD_FIXED, FIELD_FORMULA, FIELD_MANUAL,
    FieldConfig, RobotManifest, Selector, SiteLimit, Step,
)
from .field_config import FieldConfigDialog, data_type_label
from .formula_help import FormulaHelpDialog, formula_completer

_ACTION_LABELS = {
    "goto": "Navegar", "click": "Clicar", "fill": "Preencher",
    "select": "Selecionar", "press": "Tecla", "download": "Download",
}
_FIELDABLE = {"fill", "select"}
_TYPE_ITEMS = [("Fixo", FIELD_FIXED), ("Fórmula", FIELD_FORMULA),
               ("Manual (pergunta ao rodar)", FIELD_MANUAL)]


class RecordingReviewDialog(QDialog):
    def __init__(self, summary: dict, robot_name: str, parent=None, title=None):
        super().__init__(parent)
        self.summary = summary
        self.raw_steps = summary.get("steps", [])
        self.setWindowTitle(title or f"Revisar gravação — {robot_name}")
        self.resize(1000, 650)

        root = QVBoxLayout(self)

        header = QHBoxLayout()
        info = QLabel(
            f"URL inicial: {summary.get('start_url') or '(definida na gravação)'}   |   "
            f"Login/sessão: {'sim' if summary.get('has_login') else 'não'}   |   "
            f"Passos: {len(self.raw_steps)}"
        )
        info.setObjectName("AppSubtitle")
        header.addWidget(info)
        header.addStretch(1)
        help_btn = QPushButton("ƒ Fórmulas disponíveis")
        help_btn.clicked.connect(lambda: FormulaHelpDialog(self).exec())
        header.addWidget(help_btn)
        root.addLayout(header)

        self.table = QTableWidget(len(self.raw_steps), 6)
        self.table.setHorizontalHeaderLabels(
            ["#", "Ação", "Elemento", "Tipo do campo", "Valor / Fórmula / Nome", "Config."]
        )
        self.table.verticalHeader().setVisible(False)
        self.table.horizontalHeader().setSectionResizeMode(2, QHeaderView.Stretch)
        self.table.horizontalHeader().setSectionResizeMode(4, QHeaderView.Stretch)
        root.addWidget(self.table, 1)

        self._rows = []  # dict por linha (ou None)
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

            if action not in _FIELDABLE:
                self.table.setItem(i, 3, _ro_item("—"))
                self.table.setItem(i, 4, _ro_item(step.get("value", "")))
                self.table.setItem(i, 5, _ro_item(""))
                self._rows.append(None)
                continue

            existing = step.get("field") or None
            cfg = {"name": "", "data_type": DT_TEXT, "fmt": "dd/mm/yyyy", "options": []}
            init_text = step.get("value", "")
            etype = FIELD_FIXED
            if existing:
                etype = existing.get("type", FIELD_FIXED)
                if etype == FIELD_FORMULA:
                    init_text = existing.get("formula", "")
                elif etype == FIELD_MANUAL:
                    cfg = {
                        "name": existing.get("name", "") or existing.get("prompt", ""),
                        "data_type": existing.get("data_type", DT_TEXT),
                        "fmt": existing.get("fmt", "dd/mm/yyyy"),
                        "options": list(existing.get("options", []) or []),
                    }
                    init_text = cfg["name"]
                else:
                    init_text = existing.get("value", init_text)

            combo = QComboBox()
            for label, value in _TYPE_ITEMS:
                combo.addItem(label, value)
            ci = combo.findData(etype)
            if ci >= 0:
                combo.setCurrentIndex(ci)

            edit = QLineEdit(init_text)
            cfg_btn = QToolButton()
            cfg_btn.setText("⚙")
            cfg_btn.setToolTip("Configurar tipo de dado e nome do campo")

            row = {"combo": combo, "edit": edit, "cfg": cfg, "cfg_btn": cfg_btn, "step": step}
            cfg_btn.clicked.connect(lambda _c=False, r=row: self._configure(r))
            combo.currentIndexChanged.connect(lambda _idx, r=row: self._on_type_changed(r))

            self.table.setCellWidget(i, 3, combo)
            self.table.setCellWidget(i, 4, edit)
            self.table.setCellWidget(i, 5, cfg_btn)
            self._rows.append(row)
            self._fill_choices.append(
                (f"#{i} — {step.get('label') or step.get('value') or action}", i))
            self._apply_type_ui(row)

    def _on_type_changed(self, row):
        # Ao trocar p/ Manual, herda um nome inicial do rótulo do elemento.
        if row["combo"].currentData() == FIELD_MANUAL and not row["edit"].text().strip():
            row["edit"].setText(row["step"].get("label", "") or "")
        self._apply_type_ui(row)

    def _apply_type_ui(self, row):
        kind = row["combo"].currentData()
        edit, cfg_btn = row["edit"], row["cfg_btn"]
        edit.setCompleter(None)
        if kind == FIELD_FIXED:
            edit.setPlaceholderText("Valor fixo (ex.: 23/06/2026)")
            cfg_btn.setEnabled(False)
        elif kind == FIELD_FORMULA:
            edit.setPlaceholderText("Fórmula (ex.: WORKDAY(TODAY(); -1))")
            edit.setCompleter(formula_completer(edit))
            cfg_btn.setEnabled(False)
        else:  # manual
            edit.setPlaceholderText("Nome do campo (ex.: Data inicial)")
            cfg_btn.setEnabled(True)
            cfg_btn.setToolTip(f"Tipo: {data_type_label(row['cfg']['data_type'])} — clique p/ configurar")

    def _configure(self, row):
        seed = dict(row["cfg"])
        if row["edit"].text().strip():
            seed["name"] = row["edit"].text().strip()
        dlg = FieldConfigDialog(seed, self)
        if dlg.exec() == QDialog.Accepted:
            row["cfg"] = dlg.result_config()
            if row["cfg"]["name"]:
                row["edit"].setText(row["cfg"]["name"])
            self._apply_type_ui(row)

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

        def _toggle(on):
            for w in (self.max_rows, self.strategy, self.start_step, self.end_step):
                w.setEnabled(on)
        _toggle(False)
        self.limit_check.toggled.connect(_toggle)

        sl = self.summary.get("site_limit") or {}
        if sl.get("enabled"):
            self.limit_check.setChecked(True)
            self.max_rows.setValue(int(sl.get("max_rows") or 500))
            si = self.strategy.findData(sl.get("strategy", "date_partition"))
            if si >= 0:
                self.strategy.setCurrentIndex(si)
            sd = self.start_step.findData(sl.get("start_date_step", -1))
            if sd >= 0:
                self.start_step.setCurrentIndex(sd)
            ed = self.end_step.findData(sl.get("end_date_step", -1))
            if ed >= 0:
                self.end_step.setCurrentIndex(ed)
        return group

    # ---------------------------------------------------------------- saída
    def _on_accept(self):
        for i, row in enumerate(self._rows):
            if row and row["combo"].currentData() == FIELD_FORMULA:
                ok, msg = formula.validate(row["edit"].text())
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
            row = self._rows[i]
            if row is not None:
                kind = row["combo"].currentData()
                text = row["edit"].text().strip()
                if kind == FIELD_FIXED:
                    field = FieldConfig(type=FIELD_FIXED, value=text)
                elif kind == FIELD_FORMULA:
                    field = FieldConfig(type=FIELD_FORMULA, formula=text)
                else:
                    cfg = row["cfg"]
                    nm = text or cfg.get("name") or raw.get("label") or "Informe o valor"
                    field = FieldConfig(
                        type=FIELD_MANUAL, prompt=nm, name=nm,
                        data_type=cfg.get("data_type", DT_TEXT),
                        fmt=cfg.get("fmt", "dd/mm/yyyy"),
                        options=list(cfg.get("options", []) or []),
                    )
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
