"""Espelhamento da estrutura lógica (Telas/Blocos/Robôs) em pastas físicas.

Caminho físico de um robô:
    <data_root>/<tela.folder_name>/<bloco.folder_name>/<robo.folder_name>

Como os nomes das pastas-filhas são relativos, renomear uma Tela/Bloco move toda
a subárvore fisicamente sem precisar mexer nos filhos no banco.

Se uma operação de arquivo falhar por bloqueio do Windows (arquivo em uso), ela é
registrada na fila `pending_ops` e repetida depois (em background / na inicialização),
em vez de travar o programa.
"""

from __future__ import annotations

import os
import shutil

from ..db import Database


class FolderMirror:
    def __init__(self, db: Database, data_root: str):
        self.db = db
        self.root = data_root

    # ----------------------------------------------------- resolução de paths
    def screen_dir(self, screen_id: int) -> str | None:
        s = self.db.get_screen(screen_id)
        return None if s is None else os.path.join(self.root, s.folder_name)

    def block_dir(self, block_id: int) -> str | None:
        b = self.db.get_block(block_id)
        if b is None:
            return None
        s = self.db.get_screen(b.screen_id)
        if s is None:
            return None
        return os.path.join(self.root, s.folder_name, b.folder_name)

    def robot_dir(self, robot_id: int) -> str | None:
        r = self.db.get_robot(robot_id)
        if r is None:
            return None
        b = self.db.get_block(r.block_id)
        if b is None:
            return None
        s = self.db.get_screen(b.screen_id)
        if s is None:
            return None
        return os.path.join(self.root, s.folder_name, b.folder_name, r.folder_name)

    # ------------------------------------------------- operações de alto nível
    def ensure_dir(self, path: str | None) -> bool:
        if not path:
            return False
        try:
            self._raw_create(path)
            return True
        except OSError as e:
            self.db.add_pending("create", None, path, str(e))
            return False

    def move(self, src: str | None, dst: str | None) -> bool:
        if not src or not dst:
            return False
        if os.path.normcase(os.path.normpath(src)) == os.path.normcase(os.path.normpath(dst)):
            return True
        try:
            self._raw_move(src, dst)
            return True
        except OSError as e:
            self.db.add_pending("move", src, dst, str(e))
            return False

    def remove(self, path: str | None) -> bool:
        if not path:
            return False
        try:
            self._raw_remove(path)
            return True
        except OSError as e:
            self.db.add_pending("remove", path, None, str(e))
            return False

    # --------------------------------------------------- reconciliação inicial
    def reconcile(self) -> None:
        """Garante que todas as pastas do modelo existam fisicamente."""
        os.makedirs(self.root, exist_ok=True)
        for screen in self.db.list_screens():
            self.ensure_dir(os.path.join(self.root, screen.folder_name))
            for block in self.db.list_blocks(screen.id):
                bdir = os.path.join(self.root, screen.folder_name, block.folder_name)
                self.ensure_dir(bdir)
                for robot in self.db.list_robots(block.id):
                    self.ensure_dir(os.path.join(bdir, robot.folder_name))

    # ----------------------------------------------------- fila de retentativas
    def process_pending(self) -> int:
        """Tenta executar as operações pendentes. Retorna quantas concluíram."""
        done = 0
        for op in self.db.list_pending():
            try:
                op_type = op["op_type"]
                if op_type == "create":
                    self._raw_create(op["dst_path"])
                elif op_type == "move":
                    self._raw_move(op["src_path"], op["dst_path"])
                elif op_type == "remove":
                    self._raw_remove(op["src_path"])
                self.db.delete_pending(op["id"])
                done += 1
            except OSError as e:
                self.db.bump_pending(op["id"], str(e))
        return done

    # ------------------------------------------------------- operações cruas
    @staticmethod
    def _raw_create(path: str) -> None:
        os.makedirs(path, exist_ok=True)

    def _raw_move(self, src: str, dst: str) -> None:
        if not os.path.exists(src):
            # Origem já não existe: basta garantir o destino.
            os.makedirs(dst, exist_ok=True)
            return
        os.makedirs(os.path.dirname(dst) or self.root, exist_ok=True)
        if os.path.exists(dst):
            # Destino já existe: mescla o conteúdo e remove a origem esvaziada.
            self._merge(src, dst)
        else:
            os.rename(src, dst)

    def _merge(self, src: str, dst: str) -> None:
        for name in os.listdir(src):
            s = os.path.join(src, name)
            d = os.path.join(dst, name)
            if os.path.isdir(s):
                os.makedirs(d, exist_ok=True)
                self._merge(s, d)
            else:
                if os.path.exists(d):
                    base, ext = os.path.splitext(name)
                    d = os.path.join(dst, f"{base} (movido){ext}")
                shutil.move(s, d)
        # Remove a origem se ficou vazia (pode falhar se houver lock residual).
        os.rmdir(src)

    @staticmethod
    def _raw_remove(path: str) -> None:
        if os.path.isdir(path):
            shutil.rmtree(path)
        elif os.path.isfile(path):
            os.remove(path)
