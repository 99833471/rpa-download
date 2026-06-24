"""Worker em background que processa a fila de operações de arquivo pendentes.

Roda em uma QThread própria, com sua própria conexão SQLite (as conexões do
módulo db são por-thread). Tenta esvaziar a fila periodicamente e pode ser
"acordado" sob demanda logo após uma operação falhar.
"""

from __future__ import annotations

import threading

from PySide6.QtCore import QThread, Signal

from ..db import Database
from .folder_mirror import FolderMirror


class RetryWorker(QThread):
    pendingChanged = Signal(int)  # quantidade de itens ainda pendentes

    def __init__(self, db_path: str, data_root: str, interval: float = 15.0, parent=None):
        super().__init__(parent)
        self._db_path = db_path
        self._data_root = data_root
        self._interval = interval
        self._stop = threading.Event()
        self._wake = threading.Event()

    def run(self) -> None:
        db = Database(self._db_path)
        mirror = FolderMirror(db, self._data_root)
        # Primeira passada imediata ao iniciar o programa.
        self._tick(db, mirror)
        while not self._stop.is_set():
            self._wake.wait(self._interval)
            self._wake.clear()
            if self._stop.is_set():
                break
            self._tick(db, mirror)

    def _tick(self, db: Database, mirror: FolderMirror) -> None:
        try:
            mirror.process_pending()
            self.pendingChanged.emit(db.count_pending())
        except Exception:
            # O worker nunca deve derrubar o app; tenta de novo no próximo ciclo.
            pass

    def trigger(self) -> None:
        """Acorda o worker para processar a fila imediatamente."""
        self._wake.set()

    def stop(self) -> None:
        self._stop.set()
        self._wake.set()
