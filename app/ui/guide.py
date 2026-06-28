"""Janela de Guia: renderiza o GUIA.md (fonte única, também visível no GitHub)."""

from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QDialog,
    QDialogButtonBox,
    QTextBrowser,
    QVBoxLayout,
)

from ..resources import guide_path

_FALLBACK = (
    "# Guia\n\nNão foi possível carregar o guia (GUIA.md). "
    "Consulte o passo a passo no repositório do projeto no GitHub."
)


def load_guide_markdown() -> str:
    path = guide_path()
    if path:
        try:
            with open(path, "r", encoding="utf-8") as f:
                return f.read()
        except OSError:
            pass
    return _FALLBACK


class GuideDialog(QDialog):
    """Mostra o passo a passo (GUIA.md) renderizado, em tela cheia."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Guia — RPA Download")
        self.resize(900, 700)

        layout = QVBoxLayout(self)

        self.view = QTextBrowser()
        self.view.setOpenExternalLinks(True)  # links abrem no navegador
        self.view.setMarkdown(load_guide_markdown())
        layout.addWidget(self.view, 1)

        buttons = QDialogButtonBox(QDialogButtonBox.Close)
        buttons.rejected.connect(self.reject)
        buttons.accepted.connect(self.accept)
        layout.addWidget(buttons)

        self.setWindowState(self.windowState() | Qt.WindowMaximized)
