"""Ponto de entrada do AUTOMATIZADOR DOWNLOAD DE DADOS.

Funciona como app gráfico e, quando empacotado em .exe, também como despachante:
ao ser chamado com --rpa-exec / --rpa-record, o próprio executável roda o
subprocesso de execução/gravação (já que ``python -m`` não existe num app
congelado).
"""

from __future__ import annotations

import os
import sys

# Local estável de navegadores (fora do bundle) — habilita o "runner leve":
# o Chromium é baixado aqui no 1º uso e reaproveitado depois.
if not os.environ.get("PLAYWRIGHT_BROWSERS_PATH"):
    _base = os.environ.get("LOCALAPPDATA") or os.path.expanduser("~")
    os.environ["PLAYWRIGHT_BROWSERS_PATH"] = os.path.join(_base, "ms-playwright")


def _restore_std_streams() -> None:
    """No modo --windowed do PyInstaller, sys.stdout/err podem ser None.

    Reconstrói a partir dos descritores herdados (pipes do QProcess) para a
    comunicação do subprocesso com o app funcionar.
    """
    for fd, name in ((1, "stdout"), (2, "stderr")):
        if getattr(sys, name, None) is None:
            try:
                setattr(sys, name, os.fdopen(fd, "w", encoding="utf-8", buffering=1))
            except OSError:
                setattr(sys, name, open(os.devnull, "w", encoding="utf-8"))


def _dispatch_subprocess() -> None:
    """Se chamado com flag de subprocesso, executa o módulo e encerra."""
    if len(sys.argv) < 2 or sys.argv[1] not in ("--rpa-exec", "--rpa-record"):
        return
    _restore_std_streams()
    rest = sys.argv[2:]
    if sys.argv[1] == "--rpa-exec":
        from app.executor.executor_process import main as run
    else:
        from app.recorder.recorder_process import main as run
    sys.exit(run(rest))


def run_gui() -> int:
    from PySide6.QtWidgets import QApplication, QFileDialog, QMessageBox

    from app import config
    from app.bootstrap import seed_if_empty
    from app.db import Database
    from app.services.folder_mirror import FolderMirror
    from app.services.retry_worker import RetryWorker
    from app.ui.main_window import MainWindow
    from app.ui.theme import build_qss

    app = QApplication(sys.argv)
    app.setApplicationName("AUTOMATIZADOR DOWNLOAD DE DADOS")

    data_root = config.get_data_root()
    if data_root is None:
        QMessageBox.information(
            None, "Primeira execução",
            "Selecione o diretório raiz onde a pasta\n"
            f"“{config.APP_FOLDER_NAME}” será criada.",
        )
        parent = QFileDialog.getExistingDirectory(None, "Selecione o diretório raiz")
        if not parent:
            return 0
        data_root = config.initialize_root(parent)

    db = Database(config.db_path(data_root))
    mirror = FolderMirror(db, data_root)

    seed_if_empty(db, mirror)
    mirror.reconcile()

    retry_worker = RetryWorker(config.db_path(data_root), data_root)
    retry_worker.start()
    app.aboutToQuit.connect(retry_worker.stop)

    theme = config.get_theme()
    app.setStyleSheet(build_qss(theme))

    window = MainWindow(db, mirror, retry_worker, theme)
    window.show()

    return app.exec()


def main() -> int:
    return run_gui()


if __name__ == "__main__":
    _dispatch_subprocess()  # encerra aqui se for um subprocesso
    sys.exit(main())
