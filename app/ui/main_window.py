"""Janela principal: barra superior (título + alternância de tema) e o Dashboard."""

from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QHBoxLayout,
    QLabel,
    QMainWindow,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from .. import config
from .dashboard import Dashboard
from .theme import build_qss


class MainWindow(QMainWindow):
    def __init__(self, db, mirror, retry_worker, theme_name: str):
        super().__init__()
        self.db = db
        self.mirror = mirror
        self.retry = retry_worker
        self.theme_name = theme_name

        self.setWindowTitle(config.APP_DISPLAY_NAME)
        self.resize(1180, 760)

        central = QWidget()
        outer = QVBoxLayout(central)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(0)

        outer.addWidget(self._build_top_bar())

        self.dashboard = Dashboard(
            db, mirror, retry_worker, theme_name,
            status_cb=self._set_status,
        )
        outer.addWidget(self.dashboard, 1)

        self.setCentralWidget(central)
        self.statusBar().setObjectName("StatusBar")
        self._set_status("Pronto.")

        if retry_worker is not None:
            retry_worker.pendingChanged.connect(self._on_pending_changed)

    def _build_top_bar(self) -> QWidget:
        bar = QWidget()
        bar.setObjectName("TopBar")
        layout = QHBoxLayout(bar)
        layout.setContentsMargins(16, 10, 16, 10)

        title_box = QVBoxLayout()
        title_box.setSpacing(0)
        title = QLabel(config.APP_DISPLAY_NAME)
        title.setObjectName("AppTitle")
        subtitle = QLabel(config.get_data_root() or "")
        subtitle.setObjectName("AppSubtitle")
        title_box.addWidget(title)
        title_box.addWidget(subtitle)
        layout.addLayout(title_box)
        layout.addStretch(1)

        self.theme_btn = QPushButton()
        self.theme_btn.setToolTip("Alternar tema claro/escuro")
        self._update_theme_button()
        self.theme_btn.clicked.connect(self.toggle_theme)
        layout.addWidget(self.theme_btn)

        return bar

    def _update_theme_button(self) -> None:
        if self.theme_name == "dark":
            self.theme_btn.setText("☀  Tema claro (Ambev)")
        else:
            self.theme_btn.setText("🌙  Tema escuro (AB InBev)")

    def toggle_theme(self) -> None:
        self.theme_name = "light" if self.theme_name == "dark" else "dark"
        config.set_theme(self.theme_name)
        from PySide6.QtWidgets import QApplication
        QApplication.instance().setStyleSheet(build_qss(self.theme_name))
        self._update_theme_button()
        self.dashboard.set_theme(self.theme_name)

    def _set_status(self, msg: str) -> None:
        self.statusBar().showMessage(msg)

    def _on_pending_changed(self, count: int) -> None:
        if count:
            self._set_status(f"⚠ {count} operação(ões) de pasta pendente(s) — tentando em background…")
        else:
            self._set_status("Pronto.")

    def closeEvent(self, event):
        if self.retry is not None:
            self.retry.stop()
            self.retry.wait(2000)
        super().closeEvent(event)
