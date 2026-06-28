"""Teste de fumaça da Fase 1.

Valida, sem interação manual:
- Higienização de nomes.
- Banco SQLite (CRUD básico) + espelhamento físico de pastas.
- Renomear/mover/excluir refletindo nas pastas.
- Fila de retentativas (process_pending).
- Construção da janela principal em modo offscreen (sem abrir tela).

Uso:  python tests/smoke_test.py
"""

from __future__ import annotations

import os
import sys
import tempfile

# Permite importar o pacote "app" rodando a partir da raiz do projeto.
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Garante backend headless do Qt antes de importar PySide6.
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from app.bootstrap import seed_if_empty  # noqa: E402
from app.db import Database  # noqa: E402
from app.sanitize import make_unique, sanitize_name  # noqa: E402
from app.services.folder_mirror import FolderMirror  # noqa: E402

_failures = []


def check(label, cond):
    status = "OK " if cond else "FALHOU"
    print(f"  [{status}] {label}")
    if not cond:
        _failures.append(label)


def test_sanitize():
    print("== Higienização de nomes ==")
    check('remove caracteres proibidos', sanitize_name('Custos: A/B*?') == 'Custos AB')
    check('nome vazio usa fallback', sanitize_name('   ') == 'SemNome')
    check('nome reservado recebe prefixo', sanitize_name('CON') == '_CON')
    check('colapsa espaços', sanitize_name('a    b') == 'a b')
    check('dedup faz (2)', make_unique('Armazém', {'armazém'}) == 'Armazém (2)')
    check('dedup cresce', make_unique('X', {'x', 'x (2)'}) == 'X (3)')


def test_db_and_mirror(root):
    print("== Banco + espelhamento de pastas ==")
    db = Database(os.path.join(root, '.rpa', 'app.db'))
    mirror = FolderMirror(db, root)
    seed_if_empty(db, mirror)

    screens = db.list_screens()
    check('seed criou só a Home', len(screens) == 1)
    check('existe tela Home', db.get_home_screen() is not None)
    check('pasta Home existe', os.path.isdir(os.path.join(root, 'Home')))

    # Cria uma tela "Geral" + bloco "Principal" para o restante do teste.
    gfolder = make_unique(sanitize_name('Geral'), db.screen_folder_names())
    geral_id = db.add_screen('Geral', '', gfolder)
    mirror.ensure_dir(mirror.screen_dir(geral_id))
    pfolder = make_unique(sanitize_name('Principal'), db.block_folder_names(geral_id))
    pblock_id = db.add_block(geral_id, 'Principal', '', pfolder)
    mirror.ensure_dir(mirror.block_dir(pblock_id))
    check('pasta Geral/Principal existe', os.path.isdir(os.path.join(root, 'Geral', 'Principal')))

    # Cria um robô e confere a pasta física.
    geral = db.get_screen(geral_id)
    block = db.first_block_of_screen(geral.id)
    folder = make_unique(sanitize_name('Robô Custos'), db.robot_folder_names(block.id))
    rid = db.add_robot(block.id, 'Robô Custos', '', folder)
    mirror.ensure_dir(mirror.robot_dir(rid))
    robot_dir = os.path.join(root, 'Geral', 'Principal', 'Robô Custos')
    check('pasta do robô criada', os.path.isdir(robot_dir))

    # Renomeia a tela -> a subárvore inteira move fisicamente.
    old_dir = mirror.screen_dir(geral.id)
    new_folder = make_unique(sanitize_name('Armazém'), db.screen_folder_names(exclude_id=geral.id))
    db.update_screen(geral.id, 'Armazém', '', new_folder)
    mirror.move(old_dir, mirror.screen_dir(geral.id))
    check('tela renomeada moveu pasta', os.path.isdir(os.path.join(root, 'Armazém')))
    check('robô seguiu a renomeação da tela',
          os.path.isdir(os.path.join(root, 'Armazém', 'Principal', 'Robô Custos')))
    check('pasta antiga não existe mais', not os.path.isdir(old_dir))

    # Move robô para a Home (1º estágio do delete).
    home = db.get_home_screen()
    home_block = db.first_block_of_screen(home.id)
    old_robot_dir = mirror.robot_dir(rid)
    rfolder = make_unique(db.get_robot(rid).folder_name, db.robot_folder_names(home_block.id))
    db.move_robot(rid, home_block.id, rfolder)
    mirror.move(old_robot_dir, mirror.robot_dir(rid))
    check('robô movido para a Home',
          os.path.isdir(os.path.join(root, 'Home', home_block.folder_name, 'Robô Custos')))

    # Fila de retentativas: processa fila vazia sem erro.
    check('process_pending roda sem erro', mirror.process_pending() == 0)
    check('sem operações pendentes', db.count_pending() == 0)


def test_ui_construction(root):
    print("== Construção da UI (offscreen) ==")
    from PySide6.QtWidgets import QApplication

    from app.db import Database as DB
    from app.services.folder_mirror import FolderMirror as FM
    from app.ui.main_window import MainWindow

    app = QApplication.instance() or QApplication(sys.argv)
    db = DB(os.path.join(root, '.rpa', 'app.db'))
    mirror = FM(db, root)
    win = MainWindow(db, mirror, retry_worker=None, theme_name='dark')
    win.show()
    app.processEvents()
    check('MainWindow construiu com abas', win.dashboard.tabs.count() >= 2)
    # Alterna o tema sem quebrar.
    win.toggle_theme()
    app.processEvents()
    check('alternância de tema funcionou', win.theme_name == 'light')
    win.close()


def main():
    test_sanitize()
    # ignore_cleanup_errors: no Windows o arquivo .db (WAL) pode ficar em uso
    # até o processo encerrar; isso é apenas limpeza de teste, não bug do app.
    with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as root:
        test_db_and_mirror(root)
        test_ui_construction(root)

    print()
    if _failures:
        print(f"RESULTADO: {len(_failures)} verificação(ões) falharam: {_failures}")
        return 1
    print("RESULTADO: todas as verificacoes passaram - OK")
    return 0


if __name__ == "__main__":
    sys.exit(main())
