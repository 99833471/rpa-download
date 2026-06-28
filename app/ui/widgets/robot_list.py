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
NAT_H_ROLE = Qt.UserRole + 2  # altura natural do item (antes de uniformizar)
_MAX_LABEL_LINES = 6


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

        # Sem gridSize fixo: cada item dimensiona a própria altura (ver add_robot),
        # para o nome completo aparecer quebrando em linhas.
        self.setIconSize(QSize(ICON_SIZES["small"], ICON_SIZES["small"]))

        # Duplo-clique num robô executa-o.
        self.itemDoubleClicked.connect(self._on_double_click)

    def _on_double_click(self, item) -> None:
        rid = item.data(ROBOT_ID_ROLE)
        if rid is not None:
            self.executeRequested.emit(rid)

    def _ensure_icon_size(self, size_key: str) -> None:
        want = ICON_SIZES.get(size_key, ICON_SIZES["small"])
        if want > self.iconSize().width():
            self.setIconSize(QSize(want, want))

    # ------------------------------------------------------------- popular
    def add_robot(self, robot) -> None:
        self._ensure_icon_size(robot.size)
        item = QListWidgetItem(make_robot_icon(robot.name, robot.size, self.theme_name), robot.name)
        item.setData(ROBOT_ID_ROLE, robot.id)
        tip = f"{robot.name}\n\n{robot.description}" if robot.description else robot.name
        item.setToolTip(tip)
        item.setTextAlignment(Qt.AlignHCenter | Qt.AlignTop)

        # Altura da célula calculada para caber o NOME COMPLETO (quebrado em
        # linhas). Nomes muito longos limitam-se a algumas linhas + tooltip.
        cell_w = GRID_SIZES["large"][0]
        fm = self.fontMetrics()
        flags = int(Qt.TextWordWrap) | int(Qt.AlignHCenter)
        rect = fm.boundingRect(0, 0, cell_w - 14, 10000, flags, robot.name)
        text_h = min(rect.height(), fm.lineSpacing() * _MAX_LABEL_LINES)
        nat_h = self.iconSize().height() + 12 + text_h + 10
        item.setData(NAT_H_ROLE, nat_h)
        item.setSizeHint(QSize(cell_w, nat_h))
        self.addItem(item)
        self._normalize_heights()

    def _normalize_heights(self) -> None:
        """Uniformiza a altura das células pela maior, mantendo as linhas alinhadas."""
        n = self.count()
        if not n:
            return
        height = max(int(self.item(i).data(NAT_H_ROLE) or self.item(i).sizeHint().height())
                     for i in range(n))
        width = GRID_SIZES["large"][0]
        for i in range(n):
            self.item(i).setSizeHint(QSize(width, height))

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
