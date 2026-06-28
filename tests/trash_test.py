"""Testa a semântica da Home e da Lixeira (nível de dados + migração).

Uso:  python tests/trash_test.py
"""

from __future__ import annotations

import os
import sys
import tempfile

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.bootstrap import migrate, seed_if_empty  # noqa: E402
from app.db import Database  # noqa: E402
from app.sanitize import make_unique, sanitize_name  # noqa: E402
from app.services.folder_mirror import FolderMirror  # noqa: E402

_failures = []


def check(label, cond):
    print(f"  [{'OK ' if cond else 'FALHOU'}] {label}")
    if not cond:
        _failures.append(label)


def main():
    print("== Home / Lixeira ==")
    with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as root:
        db = Database(os.path.join(root, ".rpa", "app.db"))
        mirror = FolderMirror(db, root)
        seed_if_empty(db, mirror)

        screens = db.list_screens()
        check("instala só a Home", len(screens) == 1 and screens[0].is_home == 1)
        home = db.get_home_screen()
        check("Home não fala em exclusão",
              "exclus" not in (home.description or "").lower())
        check("sem Lixeira no início", db.get_trash_screen() is None)

        # Cria a Lixeira (como o dashboard faz sob demanda).
        folder = make_unique(sanitize_name("Lixeira"), db.screen_folder_names())
        sid = db.add_screen("Lixeira", "Robôs aqui aguardam exclusão definitiva.",
                            folder, is_trash=1)
        trash = db.get_trash_screen()
        check("Lixeira encontrada por is_trash", trash is not None and trash.id == sid)
        check("is_trash persiste no modelo", trash.is_trash == 1)
        check("Home e Lixeira são distintas", db.get_home_screen().id != trash.id)

        # Migração de banco antigo: Home com texto de "lixeira".
        db.update_screen(home.id, home.name, "Itens recebidos e robôs aguardando exclusão.",
                         home.folder_name)
        migrate(db)
        home2 = db.get_home_screen()
        check("migração corrige o texto antigo da Home",
              "aguardando" not in (home2.description or "").lower())

    print()
    if _failures:
        print(f"RESULTADO: {len(_failures)} falha(s): {_failures}")
        return 1
    print("RESULTADO: home/lixeira - OK")
    return 0


if __name__ == "__main__":
    sys.exit(main())
