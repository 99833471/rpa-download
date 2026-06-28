"""Inicialização: primeira execução, seed da estrutura padrão e reconciliação."""

from __future__ import annotations

from .db import Database
from .sanitize import sanitize_name
from .services.folder_mirror import FolderMirror


_HOME_DESC = "Tela padrão: robôs criados sem uma tela definida ficam aqui."


def seed_if_empty(db: Database, mirror: FolderMirror) -> None:
    """Cria a estrutura inicial na primeira vez: apenas a Tela Home (padrão).

    A Home é a única tela criada na instalação; serve para robôs criados sem uma
    tela definida. A "Lixeira" é criada sob demanda (na primeira exclusão).
    """
    if db.list_screens():
        migrate(db)
        return

    home_id = db.add_screen("Home", _HOME_DESC, sanitize_name("Home"), is_home=1)
    db.add_block(home_id, "Geral", "Robôs sem uma tela específica ficam aqui.",
                 sanitize_name("Geral"))
    mirror.reconcile()


def migrate(db: Database) -> None:
    """Ajustes para bancos de versões anteriores (não recria nada)."""
    home = db.get_home_screen()
    if home:
        d = (home.description or "").lower()
        if "exclus" in d or "aguardando" in d or "recebid" in d:
            db.update_screen(home.id, home.name, _HOME_DESC, home.folder_name)
