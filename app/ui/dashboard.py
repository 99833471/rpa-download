"""Dashboard: orquestra Telas (abas), Blocos e Robôs e conecta cada ação da UI
ao banco (db) e ao espelhamento de pastas (mirror).

Hierarquia de widgets:
    Dashboard (QTabWidget de telas)
      └─ ScreenPage (uma por tela)
           └─ QScrollArea
                └─ BlocksContainer (coluna de blocos, com DnD de reordenação)
                     └─ BlockWidget ...
                          └─ RobotList (grade de ícones com DnD)
"""

from __future__ import annotations

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QHBoxLayout,
    QLabel,
    QPushButton,
    QScrollArea,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)

from ..sanitize import make_unique, sanitize_name
from . import dialogs
from .execution_controller import ExecutionController
from .export_controller import ExportController
from .recording_controller import RecordingController
from .widgets.block_widget import BlockWidget
from .widgets.constants import BLOCK_MIME


class BlocksContainer(QWidget):
    """Coluna vertical de blocos que aceita o drop de reordenação (BLOCK_MIME)."""

    blocksReordered = Signal(list)  # nova ordem de block_ids

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setAcceptDrops(True)
        self._layout = QVBoxLayout(self)
        self._layout.setContentsMargins(0, 0, 0, 0)
        self._layout.setSpacing(14)
        self._layout.addStretch(1)

    def add_block_widget(self, widget: BlockWidget) -> None:
        self._layout.insertWidget(self._layout.count() - 1, widget)

    def block_widgets(self) -> list[BlockWidget]:
        result = []
        for i in range(self._layout.count()):
            w = self._layout.itemAt(i).widget()
            if isinstance(w, BlockWidget):
                result.append(w)
        return result

    def dragEnterEvent(self, event):
        if event.mimeData().hasFormat(BLOCK_MIME):
            event.acceptProposedAction()
        else:
            event.ignore()

    def dragMoveEvent(self, event):
        if event.mimeData().hasFormat(BLOCK_MIME):
            event.acceptProposedAction()
        else:
            event.ignore()

    def dropEvent(self, event):
        if not event.mimeData().hasFormat(BLOCK_MIME):
            event.ignore()
            return
        block_id = int(bytes(event.mimeData().data(BLOCK_MIME)).decode("utf-8"))
        widgets = self.block_widgets()
        ids = [w.block.id for w in widgets]
        if block_id not in ids:
            event.ignore()
            return

        drop_y = event.position().toPoint().y()
        target = len(ids)
        for i, w in enumerate(widgets):
            if drop_y < w.y() + w.height() / 2:
                target = i
                break

        old_index = ids.index(block_id)
        ids.pop(old_index)
        if target > old_index:
            target -= 1
        target = max(0, min(target, len(ids)))
        ids.insert(target, block_id)

        event.acceptProposedAction()
        self.blocksReordered.emit(ids)


class ScreenPage(QWidget):
    """Página de uma Tela: cabeçalho + coluna rolável de blocos."""

    def __init__(self, dashboard: "Dashboard", screen):
        super().__init__()
        self.dashboard = dashboard
        self.screen = screen

        root = QVBoxLayout(self)
        root.setContentsMargins(16, 12, 16, 12)
        root.setSpacing(10)

        header = QHBoxLayout()
        desc = QLabel(screen.description or "Sem descrição")
        desc.setObjectName("AppSubtitle")
        header.addWidget(desc)
        header.addStretch(1)
        add_block_btn = QPushButton("➕ Adicionar bloco")
        add_block_btn.setObjectName("Primary")
        add_block_btn.clicked.connect(lambda: dashboard.add_block(screen.id))
        header.addWidget(add_block_btn)
        root.addLayout(header)

        self.scroll = QScrollArea()
        self.scroll.setWidgetResizable(True)
        self.scroll.setFrameShape(QScrollArea.NoFrame)
        self.container = BlocksContainer()
        self.container.blocksReordered.connect(
            lambda ids: dashboard.reorder_blocks(self.screen.id, ids)
        )
        self.scroll.setWidget(self.container)
        root.addWidget(self.scroll, 1)

        self.empty_label = QLabel("Nenhum bloco ainda. Clique em “Adicionar bloco”.")
        self.empty_label.setObjectName("AppSubtitle")
        self.empty_label.setAlignment(Qt.AlignCenter)
        root.addWidget(self.empty_label)

        self.reload()

    def reload(self) -> None:
        # Remove blocos atuais.
        for w in self.container.block_widgets():
            w.setParent(None)
            w.deleteLater()

        blocks = self.dashboard.db.list_blocks(self.screen.id)
        self.empty_label.setVisible(not blocks)

        for block in blocks:
            bw = BlockWidget(block, self.dashboard.theme_name)
            self._wire_block(bw)
            bw.populate(self.dashboard.db.list_robots(block.id))
            self.container.add_block_widget(bw)

    def _wire_block(self, bw: BlockWidget) -> None:
        d = self.dashboard
        bw.addRobotRequested.connect(d.add_robot)
        bw.renameRequested.connect(d.rename_block)
        bw.describeRequested.connect(d.describe_block)
        bw.deleteRequested.connect(d.delete_block)
        bw.moveToScreenRequested.connect(d.move_block_to_screen)
        bw.moveUpRequested.connect(lambda bid: d.nudge_block(bid, -1))
        bw.moveDownRequested.connect(lambda bid: d.nudge_block(bid, +1))

        rl = bw.robot_list
        rl.executeRequested.connect(d.execute_robot)
        rl.renameRequested.connect(d.rename_robot)
        rl.describeRequested.connect(d.describe_robot)
        rl.redoPathRequested.connect(d.redo_robot_path)
        rl.redefineFieldsRequested.connect(d.redefine_robot_fields)
        rl.deleteRequested.connect(d.delete_robot)
        rl.moveToRequested.connect(d.move_robot_dialog)
        rl.toggleSizeRequested.connect(d.toggle_robot_size)
        rl.generateExeRequested.connect(d.generate_robot_exe)
        rl.robotDroppedExternally.connect(d.move_robot_to_block)
        rl.orderChanged.connect(d.reorder_robots)


class Dashboard(QWidget):
    def __init__(self, db, mirror, retry_worker, theme_name, status_cb=None, parent=None):
        super().__init__(parent)
        self.db = db
        self.mirror = mirror
        self.retry = retry_worker
        self.theme_name = theme_name
        self.status_cb = status_cb or (lambda msg: None)

        self.recorder = RecordingController(db, mirror, self)
        self.recorder.recordingFinished.connect(self._on_recording_finished)

        self.executor = ExecutionController(db, mirror, self)
        self.executor.statusMessage.connect(self._status)

        self.exporter = ExportController(db, mirror, self)
        self.exporter.statusMessage.connect(self._status)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(8, 8, 8, 8)

        self.tabs = QTabWidget()
        self.tabs.setMovable(True)
        self.tabs.setDocumentMode(True)
        self.tabs.tabBar().setContextMenuPolicy(Qt.CustomContextMenu)
        self.tabs.tabBar().customContextMenuRequested.connect(self._tab_context_menu)
        self.tabs.tabBar().tabMoved.connect(self._on_tabs_moved)

        add_screen_btn = QPushButton("➕ Tela")
        add_screen_btn.clicked.connect(self.add_screen)
        self.tabs.setCornerWidget(add_screen_btn, Qt.TopRightCorner)

        layout.addWidget(self.tabs)

        self._pages: dict[int, ScreenPage] = {}
        self.reload_all()

    # --------------------------------------------------------------- helpers
    def _status(self, msg: str) -> None:
        self.status_cb(msg)

    def _after_fs_change(self) -> None:
        """Acorda o worker de retry e atualiza o status (operações pendentes)."""
        if self.retry is not None:
            self.retry.trigger()
        n = self.db.count_pending()
        if n:
            self._status(f"⚠ {n} operação(ões) de pasta pendente(s) — tentando em background…")
        else:
            self._status("Pronto.")

    def set_theme(self, theme_name: str) -> None:
        self.theme_name = theme_name
        self.reload_all()

    # ---------------------------------------------------------------- telas
    def reload_all(self) -> None:
        current = self.tabs.currentIndex()
        self.tabs.blockSignals(True)
        while self.tabs.count():
            page = self.tabs.widget(0)
            self.tabs.removeTab(0)
            if page is not None:
                page.setParent(None)
                page.deleteLater()
        self._pages.clear()

        bar = self.tabs.tabBar()
        for screen in self.db.list_screens():
            page = ScreenPage(self, screen)
            label = ("🏠 " if screen.is_home else "") + screen.name
            idx = self.tabs.addTab(page, label)
            bar.setTabData(idx, screen.id)
            self.tabs.setTabToolTip(idx, screen.description or screen.name)
            self._pages[screen.id] = page

        self.tabs.blockSignals(False)
        if 0 <= current < self.tabs.count():
            self.tabs.setCurrentIndex(current)
        self._after_fs_change()

    def reload_screen(self, screen_id: int) -> None:
        page = self._pages.get(screen_id)
        if page is not None:
            page.reload()

    def _current_screen_id(self) -> int | None:
        idx = self.tabs.currentIndex()
        return self.tabs.tabBar().tabData(idx) if idx >= 0 else None

    def _on_tabs_moved(self, *_args) -> None:
        bar = self.tabs.tabBar()
        ordered = [bar.tabData(i) for i in range(self.tabs.count())]
        self.db.set_screen_positions([sid for sid in ordered if sid is not None])

    def _tab_context_menu(self, pos) -> None:
        from PySide6.QtWidgets import QMenu
        bar = self.tabs.tabBar()
        index = bar.tabAt(pos)
        if index < 0:
            return
        screen_id = bar.tabData(index)
        screen = self.db.get_screen(screen_id)
        if screen is None:
            return
        menu = QMenu(self)
        menu.addAction("✎  Renomear tela", lambda: self.rename_screen(screen_id))
        menu.addAction("📝  Editar descrição", lambda: self.describe_screen(screen_id))
        if not screen.is_home:
            menu.addSeparator()
            menu.addAction("🗑  Excluir tela", lambda: self.delete_screen(screen_id))
        menu.exec(bar.mapToGlobal(pos))

    def add_screen(self) -> None:
        name = dialogs.ask_text(self, "Nova tela", "Nome da tela:")
        if not name:
            return
        folder = make_unique(sanitize_name(name), self.db.screen_folder_names())
        sid = self.db.add_screen(name, "", folder)
        self.mirror.ensure_dir(self.mirror.screen_dir(sid))
        self.reload_all()
        # seleciona a nova tela
        bar = self.tabs.tabBar()
        for i in range(self.tabs.count()):
            if bar.tabData(i) == sid:
                self.tabs.setCurrentIndex(i)
                break
        self._after_fs_change()

    def rename_screen(self, screen_id: int) -> None:
        screen = self.db.get_screen(screen_id)
        if screen is None:
            return
        name = dialogs.ask_text(self, "Renomear tela", "Novo nome:", screen.name)
        if not name or name == screen.name:
            return
        old_dir = self.mirror.screen_dir(screen_id)
        folder = make_unique(sanitize_name(name), self.db.screen_folder_names(exclude_id=screen_id))
        self.db.update_screen(screen_id, name, screen.description, folder)
        self.mirror.move(old_dir, self.mirror.screen_dir(screen_id))
        self.reload_all()
        self._after_fs_change()

    def describe_screen(self, screen_id: int) -> None:
        screen = self.db.get_screen(screen_id)
        if screen is None:
            return
        desc = dialogs.ask_multiline(self, "Descrição da tela", "Descrição:", screen.description)
        if desc is None:
            return
        self.db.update_screen(screen_id, screen.name, desc, screen.folder_name)
        self.reload_all()

    def delete_screen(self, screen_id: int) -> None:
        screen = self.db.get_screen(screen_id)
        if screen is None or screen.is_home:
            return
        if not dialogs.confirm(
            self, "Excluir tela",
            f"Excluir a tela “{screen.name}” e TODOS os seus blocos/robôs?\n"
            "A pasta física correspondente também será removida.",
        ):
            return
        path = self.mirror.screen_dir(screen_id)
        self.db.delete_screen(screen_id)
        self.mirror.remove(path)
        self.reload_all()
        self._after_fs_change()

    # --------------------------------------------------------------- blocos
    def add_block(self, screen_id: int) -> None:
        name = dialogs.ask_text(self, "Novo bloco", "Nome do bloco:")
        if not name:
            return
        folder = make_unique(sanitize_name(name), self.db.block_folder_names(screen_id))
        bid = self.db.add_block(screen_id, name, "", folder)
        self.mirror.ensure_dir(self.mirror.block_dir(bid))
        self.reload_screen(screen_id)
        self._after_fs_change()

    def rename_block(self, block_id: int) -> None:
        block = self.db.get_block(block_id)
        if block is None:
            return
        name = dialogs.ask_text(self, "Renomear bloco", "Novo nome:", block.name)
        if not name or name == block.name:
            return
        old_dir = self.mirror.block_dir(block_id)
        folder = make_unique(
            sanitize_name(name), self.db.block_folder_names(block.screen_id, exclude_id=block_id)
        )
        self.db.update_block(block_id, name, block.description, folder)
        self.mirror.move(old_dir, self.mirror.block_dir(block_id))
        self.reload_screen(block.screen_id)
        self._after_fs_change()

    def describe_block(self, block_id: int) -> None:
        block = self.db.get_block(block_id)
        if block is None:
            return
        desc = dialogs.ask_multiline(self, "Descrição do bloco", "Descrição:", block.description)
        if desc is None:
            return
        self.db.update_block(block_id, block.name, desc, block.folder_name)
        self.reload_screen(block.screen_id)

    def delete_block(self, block_id: int) -> None:
        block = self.db.get_block(block_id)
        if block is None:
            return
        if not dialogs.confirm(
            self, "Excluir bloco",
            f"Excluir o bloco “{block.name}” e todos os seus robôs?",
        ):
            return
        path = self.mirror.block_dir(block_id)
        screen_id = block.screen_id
        self.db.delete_block(block_id)
        self.mirror.remove(path)
        self.reload_screen(screen_id)
        self._after_fs_change()

    def reorder_blocks(self, screen_id: int, ordered_ids: list[int]) -> None:
        self.db.set_block_positions(screen_id, ordered_ids)
        self.reload_screen(screen_id)

    def nudge_block(self, block_id: int, delta: int) -> None:
        block = self.db.get_block(block_id)
        if block is None:
            return
        ids = [b.id for b in self.db.list_blocks(block.screen_id)]
        i = ids.index(block_id)
        j = i + delta
        if 0 <= j < len(ids):
            ids[i], ids[j] = ids[j], ids[i]
            self.db.set_block_positions(block.screen_id, ids)
            self.reload_screen(block.screen_id)

    def move_block_to_screen(self, block_id: int) -> None:
        block = self.db.get_block(block_id)
        if block is None:
            return
        options = [
            (("🏠 " if s.is_home else "") + s.name, s.id)
            for s in self.db.list_screens() if s.id != block.screen_id
        ]
        target = dialogs.choose(self, "Mover bloco", "Mover para a tela:", options)
        if target is None:
            return
        old_dir = self.mirror.block_dir(block_id)
        old_screen = block.screen_id
        folder = make_unique(block.folder_name, self.db.block_folder_names(target))
        self.db.move_block(block_id, target, folder)
        self.mirror.move(old_dir, self.mirror.block_dir(block_id))
        self.reload_screen(old_screen)
        self.reload_screen(target)
        self._after_fs_change()

    # ---------------------------------------------------------------- robôs
    def add_robot(self, block_id: int) -> None:
        name = dialogs.ask_text(self, "Novo robô", "Nome do robô:")
        if not name:
            return
        folder = make_unique(sanitize_name(name), self.db.robot_folder_names(block_id))
        rid = self.db.add_robot(block_id, name, "", folder)
        self.mirror.ensure_dir(self.mirror.robot_dir(rid))
        block = self.db.get_block(block_id)
        self.reload_screen(block.screen_id)
        self._after_fs_change()
        if dialogs.confirm(
            self, "Gravar caminho",
            f"Robô “{name}” criado.\nDeseja gravar o caminho (abrir o navegador) agora?",
        ):
            self.recorder.record(rid)

    def rename_robot(self, robot_id: int) -> None:
        robot = self.db.get_robot(robot_id)
        if robot is None:
            return
        name = dialogs.ask_text(self, "Renomear robô", "Novo nome:", robot.name)
        if not name or name == robot.name:
            return
        old_dir = self.mirror.robot_dir(robot_id)
        folder = make_unique(
            sanitize_name(name), self.db.robot_folder_names(robot.block_id, exclude_id=robot_id)
        )
        self.db.update_robot(robot_id, name=name, folder_name=folder)
        self.mirror.move(old_dir, self.mirror.robot_dir(robot_id))
        self._reload_screen_of_block(robot.block_id)
        self._after_fs_change()

    def describe_robot(self, robot_id: int) -> None:
        robot = self.db.get_robot(robot_id)
        if robot is None:
            return
        desc = dialogs.ask_multiline(self, "Descrição do robô", "Descrição:", robot.description)
        if desc is None:
            return
        self.db.update_robot(robot_id, description=desc)
        self._reload_screen_of_block(robot.block_id)

    def toggle_robot_size(self, robot_id: int) -> None:
        robot = self.db.get_robot(robot_id)
        if robot is None:
            return
        self.db.update_robot(robot_id, size="small" if robot.size == "large" else "large")
        self._reload_screen_of_block(robot.block_id)

    def delete_robot(self, robot_id: int) -> None:
        robot = self.db.get_robot(robot_id)
        if robot is None:
            return
        block = self.db.get_block(robot.block_id)
        screen = self.db.get_screen(block.screen_id)
        home = self.db.get_home_screen()

        if screen and home and screen.id == home.id:
            # Já está na Home -> exclusão definitiva.
            if not dialogs.confirm(
                self, "Excluir definitivamente",
                f"Excluir permanentemente o robô “{robot.name}”?\n"
                "A pasta física (incluindo sessões/cache) será removida.",
            ):
                return
            path = self.mirror.robot_dir(robot_id)
            self.db.delete_robot(robot_id)
            self.mirror.remove(path)
            self.reload_screen(home.id)
            self._after_fs_change()
        else:
            # Primeiro estágio: move para a Home antes da exclusão definitiva.
            home_block = self.db.first_block_of_screen(home.id) if home else None
            if home is None or home_block is None:
                dialogs.info(self, "Home indisponível", "A tela Home não possui um bloco de destino.")
                return
            self.move_robot_to_block(robot_id, home_block.id)
            dialogs.info(
                self, "Movido para a Home",
                f"O robô “{robot.name}” foi movido para a tela Home.\n"
                "Para excluí-lo definitivamente, apague-o novamente lá.",
            )

    def move_robot_dialog(self, robot_id: int) -> None:
        robot = self.db.get_robot(robot_id)
        if robot is None:
            return
        screen_opts = [
            (("🏠 " if s.is_home else "") + s.name, s.id) for s in self.db.list_screens()
        ]
        screen_id = dialogs.choose(self, "Mover robô", "Tela de destino:", screen_opts)
        if screen_id is None:
            return
        block_opts = [(b.name, b.id) for b in self.db.list_blocks(screen_id)]
        if not block_opts:
            dialogs.info(self, "Sem blocos", "A tela escolhida não possui blocos.")
            return
        block_id = dialogs.choose(self, "Mover robô", "Bloco de destino:", block_opts)
        if block_id is None:
            return
        self.move_robot_to_block(robot_id, block_id)

    def move_robot_to_block(self, robot_id: int, target_block_id: int) -> None:
        robot = self.db.get_robot(robot_id)
        if robot is None or robot.block_id == target_block_id:
            return
        source_block_id = robot.block_id
        old_dir = self.mirror.robot_dir(robot_id)
        folder = make_unique(robot.folder_name, self.db.robot_folder_names(target_block_id))
        self.db.move_robot(robot_id, target_block_id, folder)
        self.mirror.move(old_dir, self.mirror.robot_dir(robot_id))
        self._reload_screen_of_block(source_block_id)
        self._reload_screen_of_block(target_block_id)
        self._after_fs_change()

    def reorder_robots(self, block_id: int, ordered_ids: list[int]) -> None:
        self.db.set_robot_positions(block_id, ordered_ids)

    def execute_robot(self, robot_id: int) -> None:
        self.executor.run(robot_id)

    def redo_robot_path(self, robot_id: int) -> None:
        robot = self.db.get_robot(robot_id)
        if robot is None:
            return
        if not dialogs.confirm(
            self, "Refazer caminho",
            f"Regravar o robô “{robot.name}” do zero?\n"
            "A automação anterior só será substituída se você concluir e salvar.",
        ):
            return
        self.recorder.record(robot_id, reuse_session=True)

    def generate_robot_exe(self, robot_id: int) -> None:
        self.exporter.export(robot_id)

    def redefine_robot_fields(self, robot_id: int) -> None:
        import os

        from PySide6.QtWidgets import QDialog

        from ..robot_manifest import RobotManifest
        from .recording_review import RecordingReviewDialog

        robot = self.db.get_robot(robot_id)
        if robot is None:
            return
        path = os.path.join(self.mirror.robot_dir(robot_id), "robot.json")
        if not os.path.isfile(path):
            dialogs.info(
                self, "Robô sem caminho",
                "Este robô ainda não foi gravado. Use “Refazer caminho” primeiro.",
            )
            return
        try:
            manifest = RobotManifest.load(path)
        except (OSError, ValueError):
            dialogs.info(self, "Robô inválido", "Não foi possível ler o robot.json.")
            return
        if not any(s.field for s in manifest.steps):
            dialogs.info(self, "Sem campos", "Este robô não tem campos de preenchimento para redefinir.")
            return

        dlg = RecordingReviewDialog(
            manifest.to_dict(), robot.name, self,
            title=f"Redefinir campos — {robot.name}",
        )
        if dlg.exec() == QDialog.Accepted:
            new_manifest = dlg.build_manifest(robot.name, session_file=manifest.session_file)
            new_manifest.created_at = manifest.created_at
            new_manifest.save(path)
            self._status(f"Campos do robô “{robot.name}” atualizados.")
            dialogs.info(self, "Campos atualizados", "Os campos do robô foram salvos.")

    def _on_recording_finished(self, robot_id: int, saved: bool) -> None:
        robot = self.db.get_robot(robot_id)
        if robot is not None:
            self._reload_screen_of_block(robot.block_id)
        if saved:
            self._status("Robô gravado com sucesso.")
        else:
            self._status("Gravação descartada (nenhuma alteração salva).")

    # ----------------------------------------------------------- utilidades
    def _reload_screen_of_block(self, block_id: int) -> None:
        block = self.db.get_block(block_id)
        if block is not None:
            self.reload_screen(block.screen_id)
