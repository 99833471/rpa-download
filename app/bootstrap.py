"""Inicialização: primeira execução, seed da estrutura padrão e reconciliação."""

from __future__ import annotations

from .db import Database
from .sanitize import sanitize_name
from .services.folder_mirror import FolderMirror


def seed_if_empty(db: Database, mirror: FolderMirror) -> None:
    """Cria a estrutura inicial na primeira vez: Tela Home + uma Tela de exemplo."""
    if db.list_screens():
        return

    # Tela Home (destino de robôs deletados antes da exclusão definitiva).
    home_id = db.add_screen("Home", "Itens recebidos e robôs aguardando exclusão.",
                            sanitize_name("Home"), is_home=1)
    db.add_block(home_id, "Recebidos", "Robôs movidos para cá antes de excluir.",
                 sanitize_name("Recebidos"))

    # Tela de exemplo para o usuário começar.
    geral_id = db.add_screen("Geral", "Tela inicial de exemplo.", sanitize_name("Geral"))
    db.add_block(geral_id, "Principal", "Arraste seus robôs para cá.", sanitize_name("Principal"))

    mirror.reconcile()
