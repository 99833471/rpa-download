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
    from PySide6.QtGui import QIcon
    from PySide6.QtWidgets import QApplication

    from app import config
    from app.bootstrap import seed_if_empty
    from app.db import Database
    from app.resources import icon_path
    from app.services.folder_icon import set_folder_icon
    from app.services.folder_mirror import FolderMirror
    from app.services.retry_worker import RetryWorker
    from app.ui.main_window import MainWindow
    from app.ui.theme import build_qss

    # Auto-instalação: no .exe, copia-se para %LOCALAPPDATA%\Programs\RPA Download
    # e reabre de lá (uma vez). Em validação/teste (RPA_NO_SHORTCUTS) não instala.
    if getattr(sys, "frozen", False) and not os.environ.get("RPA_NO_SHORTCUTS"):
        try:
            from app.installer import ensure_installed
            if ensure_installed():
                return 0
        except Exception:
            pass

    app = QApplication(sys.argv)
    app.setApplicationName(config.APP_DISPLAY_NAME)
    app.setWindowIcon(QIcon(icon_path()))

    # Pasta de dados criada automaticamente no melhor local (sem admin); migra os
    # dados de uma pasta antiga escolhida em versões anteriores, se houver.
    data_root = config.ensure_data_root()

    db = Database(config.db_path(data_root))
    mirror = FolderMirror(db, data_root)

    seed_if_empty(db, mirror)
    mirror.reconcile()
    set_folder_icon(data_root, icon_path())  # ícone na pasta de dados (Windows)

    # Atalhos (Documentos + Menu Iniciar / pesquisável) — só no executável.
    # RPA_NO_SHORTCUTS desliga (usado na validação, p/ não criar atalho de teste).
    if getattr(sys, "frozen", False) and not os.environ.get("RPA_NO_SHORTCUTS"):
        try:
            from app.shortcuts import ensure_shortcuts
            ensure_shortcuts(sys.executable, config)
        except Exception:
            pass

    retry_worker = RetryWorker(config.db_path(data_root), data_root)
    retry_worker.start()
    app.aboutToQuit.connect(retry_worker.stop)

    theme = config.get_theme()
    app.setStyleSheet(build_qss(theme))

    window = MainWindow(db, mirror, retry_worker, theme)
    window.showMaximized()  # abre ocupando a tela toda

    return app.exec()


def main() -> int:
    return run_gui()


if __name__ == "__main__":
    _dispatch_subprocess()  # encerra aqui se for um subprocesso
    sys.exit(main())
