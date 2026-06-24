"""Valida a fila de retry com um bloqueio real de arquivo + o RetryWorker (QThread).

Simula o cenário do requisito: tentar mover uma pasta cujo arquivo está em uso,
a operação cai na fila, e depois (com o arquivo liberado) o worker em background
conclui a operação automaticamente.

Uso:  python tests/worker_test.py
"""

from __future__ import annotations

import os
import sys
import tempfile
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from app.db import Database  # noqa: E402
from app.services.folder_mirror import FolderMirror  # noqa: E402
from app.services.retry_worker import RetryWorker  # noqa: E402

_failures = []


def check(label, cond):
    print(f"  [{'OK ' if cond else 'FALHOU'}] {label}")
    if not cond:
        _failures.append(label)


def main():
    from PySide6.QtCore import QCoreApplication

    app = QCoreApplication.instance() or QCoreApplication(sys.argv)

    with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as root:
        db = Database(os.path.join(root, ".rpa", "app.db"))
        mirror = FolderMirror(db, root)

        src = os.path.join(root, "Origem")
        dst = os.path.join(root, "Destino")
        os.makedirs(src)
        locked_path = os.path.join(src, "arquivo.txt")
        handle = open(locked_path, "w", encoding="utf-8")
        handle.write("em uso")
        handle.flush()

        print("== Bloqueio do Windows -> fila de retry ==")
        ok = mirror.move(src, dst)
        check("move falhou e NÃO travou o programa", ok is False)
        check("operação foi enfileirada", db.count_pending() == 1)
        check("pasta de origem ainda existe (lock)", os.path.isdir(src))

        # Libera o arquivo e deixa o worker em background concluir.
        handle.close()
        print("== Worker em background conclui a operação ==")
        worker = RetryWorker(os.path.join(root, ".rpa", "app.db"), root, interval=0.3)
        worker.start()

        deadline = time.time() + 8
        while time.time() < deadline and db.count_pending() > 0:
            app.processEvents()
            time.sleep(0.1)

        worker.stop()
        worker.wait(3000)

        check("fila esvaziou após liberar o lock", db.count_pending() == 0)
        check("pasta movida para o destino", os.path.isdir(dst))
        check("arquivo chegou no destino", os.path.isfile(os.path.join(dst, "arquivo.txt")))
        check("origem removida", not os.path.isdir(src))

    print()
    if _failures:
        print(f"RESULTADO: {len(_failures)} falha(s): {_failures}")
        return 1
    print("RESULTADO: fila de retry + worker - OK")
    return 0


if __name__ == "__main__":
    sys.exit(main())
