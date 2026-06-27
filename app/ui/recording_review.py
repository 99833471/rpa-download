"""Diálogo de revisão pós-gravação (também usado em "Redefinir campos").

Cada passo (clique, tecla, preenchimento, seleção) aparece com um NOME sugerido
(editável) e a opção "O QUE FAZER":
- Clique/Tecla: "Repetir (normal)" ou "Clicar se aparecer (opcional)" — este último
  para pop-ups/avaliações que às vezes aparecem (na execução é pulado sem erro).
- Preencher/Selecionar: "Fixo (repete o gravado)" / "Fórmula" / "Manual".
Também coleta o questionário de limites do site. Ao confirmar, monta o RobotManifest.
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
from .field_config import FieldConfigDialog
from .formula_help import FormulaHelpDialog, formula_completer

_ACTION_LABELS = {
    "goto": "Navegar", "click": "Clicar", "fill": "Preencher",
    "select": "Selecionar", "press": "Tecla", "download": "Download",
}
_CLICKABLE = {"click", "press"}
_FIELDABLE = {"fill", "select"}
_CLICK_ITEMS = [("Repetir (normal)", False), ("Clicar se aparecer (opcional)", True)]
_FILL_ITEMS = [("Fixo (repete o gravado)", FIELD_FIXED),
               ("Fórmula", FIELD_FORMULA),
               ("Manual (pergunta ao rodar)", FIELD_MANUAL)]


def _suggest_name(step: dict) -> str:
    if step.get("name"):
        return step["name"]
    fld = step.get("field") or {}
    if fld.get("name"):
        return fld["name"]
    return (step.get("label") or step.get("value")
            or _ACTION_LABELS.get(step.get("action", ""), step.get("action", "")))


class RecordingReviewDialog(QDialog):
    def __init__(self, summary: dict, robot_name: str, parent=None, title=None):
        super().__init__(parent)
        self.summary = summary
        self.raw_steps = summary.get("steps", [])
        self.setWindowTitle(title or f"Revisar gravação — {robot_name}")
        self.resize(1040, 660)

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
            ["#", "Ação", "Nome (sugerido, editável)", "O que fazer", "Valor / Fórmula", "⚙"]
        )
        self.table.verticalHeader().setVisible(False)
        self.table.horizontalHeader().setSectionResizeMode(2, QHeaderView.Stretch)
        self.table.horizontalHeader().setSectionResizeMode(4, QHeaderView.Stretch)
        root.addWidget(self.table, 1)

        self._rows = []
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
            self.table.setItem(i, 0, _ro(str(i)))
            self.table.setItem(i, 1, _ro(_ACTION_LABELS.get(action, action)))

            if action in _CLICKABLE:
                self._build_click_row(i, step)
            elif action in _FIELDABLE:
                self._build_field_row(i, step)
            else:  # goto / download
                self.table.setItem(i, 2, _ro(step.get("label") or step.get("url") or step.get("value") or ""))
                self.table.setItem(i, 3, _ro("—"))
                self.table.setItem(i, 4, _ro(""))
                self.table.setItem(i, 5, _ro(""))
                self._rows.append(None)

    def _build_click_row(self, i, step):
        name = QLineEdit(_suggest_name(step))
        combo = QComboBox()
        for label, value in _CLICK_ITEMS:
            combo.addItem(label, value)
        ci = combo.findData(bool(step.get("optional", False)))
        if ci >= 0:
            combo.setCurrentIndex(ci)
        self.table.setCellWidget(i, 2, name)
        self.table.setCellWidget(i, 3, combo)
        self.table.setItem(i, 4, _ro(""))
        self.table.setItem(i, 5, _ro(""))
        self._rows.append({"action": step.get("action"), "name": name, "mode": combo,
                           "value": None, "cfg": None, "cfg_btn": None, "step": step})

    def _build_field_row(self, i, step):
        name = QLineEdit(_suggest_name(step))
        combo = QComboBox()
        for label, value in _FILL_ITEMS:
            combo.addItem(label, value)

        existing = step.get("field") or None
        init_value = step.get("value", "")
        cfg = {"name": "", "data_type": DT_TEXT, "fmt": "dd/mm/yyyy", "options": []}
        etype = FIELD_FIXED
        if existing:
            etype = existing.get("type", FIELD_FIXED)
            if etype == FIELD_FORMULA:
                init_value = existing.get("formula", "")
            elif etype == FIELD_MANUAL:
                cfg = {"name": existing.get("name", "") or existing.get("prompt", ""),
                       "data_type": existing.get("data_type", DT_TEXT),
                       "fmt": existing.get("fmt", "dd/mm/yyyy"),
                       "options": list(existing.get("options", []) or [])}
            else:
                init_value = existing.get("value", init_value)
        ci = combo.findData(etype)
        if ci >= 0:
            combo.setCurrentIndex(ci)

        value = QLineEdit(init_value)
        cfg_btn = QToolButton()
        cfg_btn.setText("⚙")
        cfg_btn.setToolTip("Configurar tipo de dado (campos Manual)")

        row = {"action": step.get("action"), "name": name, "mode": combo,
               "value": value, "cfg": cfg, "cfg_btn": cfg_btn, "step": step}
        combo.currentIndexChanged.connect(lambda _i, r=row: self._apply_field_mode(r))
        cfg_btn.clicked.connect(lambda _c=False, r=row: self._configure(r))

        self.table.setCellWidget(i, 2, name)
        self.table.setCellWidget(i, 3, combo)
        self.table.setCellWidget(i, 4, value)
        self.table.setCellWidget(i, 5, cfg_btn)
        self._rows.append(row)
        self._fill_choices.append((f"#{i} — {_suggest_name(step)}", i))
        self._apply_field_mode(row)

    def _apply_field_mode(self, row):
        kind = row["mode"].currentData()
        value, cfg_btn = row["value"], row["cfg_btn"]
        value.setCompleter(None)
        if kind == FIELD_FIXED:
            value.setEnabled(True)
            value.setPlaceholderText("Valor fixo (ex.: 23/06/2026)")
            cfg_btn.setEnabled(False)
        elif kind == FIELD_FORMULA:
            value.setEnabled(True)
            value.setPlaceholderText("Fórmula (ex.: WORKDAY(TODAY(); -1))")
            value.setCompleter(formula_completer(value))
            cfg_btn.setEnabled(False)
        else:  # manual
            value.setEnabled(False)
            value.setPlaceholderText("(perguntado ao rodar)")
            cfg_btn.setEnabled(True)

    def _configure(self, row):
        seed = dict(row["cfg"])
        if row["name"].text().strip():
            seed["name"] = row["name"].text().strip()
        dlg = FieldConfigDialog(seed, self)
        if dlg.exec() == QDialog.Accepted:
            row["cfg"] = dlg.result_config()
            if row["cfg"]["name"]:
                row["name"].setText(row["cfg"]["name"])

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
            if row and row["action"] in _FIELDABLE and row["mode"].currentData() == FIELD_FORMULA:
                ok, msg = formula.validate(row["value"].text())
                if not ok:
                    QMessageBox.warning(self, "Fórmula inválida",
                                        f"Passo #{i}: {msg}\n\nCorrija a fórmula antes de salvar.")
                    return
        self.accept()

    def build_manifest(self, name: str, session_file: str = "session.bin") -> RobotManifest:
        steps = []
        for i, raw in enumerate(self.raw_steps):
            selectors = [Selector(type=s.get("type", "css"), value=s.get("value", ""))
                         for s in raw.get("selectors", [])]
            row = self._rows[i]
            field = None
            optional = False
            step_name = raw.get("label", "") or ""
            if row is not None:
                step_name = row["name"].text().strip() or step_name
                if row["action"] in _CLICKABLE:
                    optional = bool(row["mode"].currentData())
                elif row["action"] in _FIELDABLE:
                    kind = row["mode"].currentData()
                    text = row["value"].text().strip()
                    if kind == FIELD_FIXED:
                        field = FieldConfig(type=FIELD_FIXED, value=text)
                    elif kind == FIELD_FORMULA:
                        field = FieldConfig(type=FIELD_FORMULA, formula=text)
                    else:
                        cfg = row["cfg"]
                        nm = step_name or cfg.get("name") or "Informe o valor"
                        field = FieldConfig(type=FIELD_MANUAL, prompt=nm, name=nm,
                                            data_type=cfg.get("data_type", DT_TEXT),
                                            fmt=cfg.get("fmt", "dd/mm/yyyy"),
                                            options=list(cfg.get("options", []) or []))
            steps.append(Step(
                action=raw.get("action", ""),
                selectors=selectors,
                url=raw.get("url", ""),
                value=raw.get("value", ""),
                tag=raw.get("tag", ""),
                label=raw.get("label", ""),
                field=field,
                name=step_name,
                optional=optional,
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


def _ro(text: str) -> QTableWidgetItem:
    item = QTableWidgetItem(text)
    item.setFlags(Qt.ItemIsEnabled)
    return item
