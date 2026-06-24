"""Diálogos auxiliares reutilizáveis."""

from __future__ import annotations

from PySide6.QtWidgets import (
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QInputDialog,
    QLabel,
    QMessageBox,
    QVBoxLayout,
)


def ask_text(parent, title, label, default="") -> str | None:
    text, ok = QInputDialog.getText(parent, title, label, text=default)
    if not ok:
        return None
    return text.strip()


def ask_multiline(parent, title, label, default="") -> str | None:
    text, ok = QInputDialog.getMultiLineText(parent, title, label, default)
    if not ok:
        return None
    return text.strip()


def confirm(parent, title, text) -> bool:
    res = QMessageBox.question(
        parent, title, text,
        QMessageBox.Yes | QMessageBox.No, QMessageBox.No,
    )
    return res == QMessageBox.Yes


def info(parent, title, text) -> None:
    QMessageBox.information(parent, title, text)


def choose(parent, title, label, options: list[tuple[str, object]]):
    """Combo de escolha. ``options`` = [(rótulo, valor)]. Retorna valor ou None."""
    if not options:
        return None
    dlg = QDialog(parent)
    dlg.setWindowTitle(title)
    layout = QVBoxLayout(dlg)
    layout.addWidget(QLabel(label))
    combo = QComboBox()
    for text, value in options:
        combo.addItem(text, value)
    layout.addWidget(combo)
    buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
    buttons.accepted.connect(dlg.accept)
    buttons.rejected.connect(dlg.reject)
    layout.addWidget(buttons)
    if dlg.exec() == QDialog.Accepted:
        return combo.currentData()
    return None
