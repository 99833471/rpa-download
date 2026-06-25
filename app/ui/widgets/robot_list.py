"""Grade de ícones de robôs dentro de um Bloco.

Suporta:
- Reordenar robôs dentro do mesmo bloco (drag-and-drop interno).
- Arrastar um robô para a grade de outro bloco (move entre blocos / telas visíveis).
- Menu de contexto (botão direito) com as ações do robô.
"""

from __future__ import annotations

from PySide6.QtCore import QSize, Qt, Signal
from PySide6.QtWidgets import QAbstractItemView, QListWidget, QListWidgetItem, QMenu

from ..theme import GRID_SIZES, ICON_SIZES, make_robot_icon
from .constants import BLOCK_MIME

ROBOT_ID_ROLE = Qt.UserRole + 1


class RobotList(QListWidget):
    # Ações do menu de contexto (carregam o robot_id):
    executeRequested = Signal(int)
    renameRequested = Signal(int)
    describeRequested = Signal(int)
    redoPathRequested = Signal(int)
    redefineFieldsRequested = Signal(int)
    deleteRequested = Signal(int)
    moveToRequested = Signal(int)
    toggleSizeRequested = Signal(int)
    generateExeRequested = Signal(int)
    openFolderRequested = Signal(int)

    # Drag-and-drop:
    robotDroppedExternally = Signal(int, int)  # robot_id, target_block_id
    orderChanged = Signal(int, list)           # block_id, [robot_ids ordenados]

    def __init__(self, block_id: int, theme_name: str, parent=None):
        super().__init__(parent)
        self.block_id = block_id
        self.theme_name = theme_name

        self.setViewMode(QListWidget.IconMode)
        self.setFlow(QListWidget.LeftToRight)
        self.setWrapping(True)
        self.setResizeMode(QListWidget.Adjust)
        self.setMovement(QListWidget.Snap)
        self.setUniformItemSizes(False)
        self.setWordWrap(True)
        self.setSpacing(6)
        self.setSelectionMode(QAbstractItemView.SingleSelection)

        self.setDragEnabled(True)
        self.setAcceptDrops(True)
        self.setDropIndicatorShown(True)
        self.setDragDropMode(QAbstractItemView.DragDrop)
        self.setDefaultDropAction(Qt.MoveAction)

        self._apply_grid("large")

    def _apply_grid(self, size_key: str) -> None:
        gw, gh = GRID_SIZES.get(size_key, GRID_SIZES["large"])
        self.setGridSize(QSize(gw, gh))
        self.setIconSize(QSize(ICON_SIZES.get(size_key, 84), ICON_SIZES.get(size_key, 84)))

    # ------------------------------------------------------------- popular
    def add_robot(self, robot) -> None:
        item = QListWidgetItem(make_robot_icon(robot.name, robot.size, self.theme_name), robot.name)
        item.setData(ROBOT_ID_ROLE, robot.id)
        item.setToolTip(robot.description or robot.name)
        item.setTextAlignment(Qt.AlignHCenter | Qt.AlignTop)
        # Ajusta a grade ao maior ícone presente (mantém alinhamento agradável).
        if robot.size == "large":
            self._apply_grid("large")
        self.addItem(item)

    def robot_ids_in_order(self) -> list[int]:
        return [self.item(i).data(ROBOT_ID_ROLE) for i in range(self.count())]

    # --------------------------------------------------------- menu contexto
    def contextMenuEvent(self, event):
        item = self.itemAt(event.pos())
        if item is None:
            return
        robot_id = item.data(ROBOT_ID_ROLE)
        menu = QMenu(self)
        menu.addAction("▶  Executar", lambda: self.executeRequested.emit(robot_id))
        menu.addSeparator()
        menu.addAction("✎  Renomear", lambda: self.renameRequested.emit(robot_id))
        menu.addAction("📝  Adicionar descrição", lambda: self.describeRequested.emit(robot_id))
        menu.addAction("🎬  Refazer caminho", lambda: self.redoPathRequested.emit(robot_id))
        menu.addAction("🛠  Redefinir campos", lambda: self.redefineFieldsRequested.emit(robot_id))
        menu.addAction("↔  Alternar tamanho do ícone", lambda: self.toggleSizeRequested.emit(robot_id))
        menu.addAction("➦  Mover para…", lambda: self.moveToRequested.emit(robot_id))
        menu.addAction("📂  Abrir pasta de downloads", lambda: self.openFolderRequested.emit(robot_id))
        menu.addSeparator()
        menu.addAction("⤓  Gerar executável (.exe)", lambda: self.generateExeRequested.emit(robot_id))
        menu.addSeparator()
        menu.addAction("🗑  Deletar", lambda: self.deleteRequested.emit(robot_id))
        menu.exec(event.globalPos())

    # ----------------------------------------------------------- drag & drop
    def dragEnterEvent(self, event):
        if event.mimeData().hasFormat(BLOCK_MIME):
            # Arrasto de Bloco: ignora para propagar ao container de blocos.
            event.ignore()
        elif isinstance(event.source(), RobotList):
            event.acceptProposedAction()
        else:
            super().dragEnterEvent(event)

    def dragMoveEvent(self, event):
        if event.mimeData().hasFormat(BLOCK_MIME):
            event.ignore()
        elif isinstance(event.source(), RobotList):
            event.acceptProposedAction()
        else:
            super().dragMoveEvent(event)

    def dropEvent(self, event):
        source = event.source()
        if isinstance(source, RobotList) and source is not self:
            # Robô vindo de outro bloco -> mover.
            item = source.currentItem()
            if item is not None:
                robot_id = item.data(ROBOT_ID_ROLE)
                self.robotDroppedExternally.emit(robot_id, self.block_id)
            event.acceptProposedAction()
        else:
            # Reordenação interna.
            super().dropEvent(event)
            self.orderChanged.emit(self.block_id, self.robot_ids_in_order())
