"""Ponto de entrada do AUTOMATIZADOR DOWNLOAD DE DADOS (Fase 1 - Fundação)."""

from __future__ import annotations

import sys

from PySide6.QtWidgets import QApplication, QFileDialog, QMessageBox

from app import config
from app.bootstrap import seed_if_empty
from app.db import Database
from app.services.folder_mirror import FolderMirror
from app.services.retry_worker import RetryWorker
from app.ui.main_window import MainWindow
from app.ui.theme import build_qss


def _choose_root(app: QApplication) -> str | None:
    """Fluxo de primeira execução: o usuário escolhe o diretório raiz."""
    QMessageBox.information(
        None,
        "Primeira execução",
        "Selecione o diretório raiz onde a pasta\n"
        f"“{config.APP_FOLDER_NAME}” será criada.",
    )
    parent = QFileDialog.getExistingDirectory(None, "Selecione o diretório raiz")
    if not parent:
        return None
    return config.initialize_root(parent)


def main() -> int:
    app = QApplication(sys.argv)
    app.setApplicationName("AUTOMATIZADOR DOWNLOAD DE DADOS")

    data_root = config.get_data_root()
    if data_root is None:
        data_root = _choose_root(app)
        if data_root is None:
            return 0  # usuário cancelou

    db = Database(config.db_path(data_root))
    mirror = FolderMirror(db, data_root)

    seed_if_empty(db, mirror)
    mirror.reconcile()  # recria pastas faltantes / enfileira bloqueios

    retry_worker = RetryWorker(config.db_path(data_root), data_root)
    retry_worker.start()
    app.aboutToQuit.connect(retry_worker.stop)

    theme = config.get_theme()
    app.setStyleSheet(build_qss(theme))

    window = MainWindow(db, mirror, retry_worker, theme)
    window.show()

    return app.exec()


if __name__ == "__main__":
    sys.exit(main())
