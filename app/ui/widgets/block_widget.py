"""Cartão de Bloco (formato landscape) que agrupa robôs.

Cabeçalho com alça de arrasto (⠿) para reordenar blocos via drag-and-drop,
título, descrição e ações. A grade de robôs tem altura mínima para ~3 linhas.
"""

from __future__ import annotations

from PySide6.QtCore import QMimeData, Qt, Signal
from PySide6.QtGui import QDrag
from PySide6.QtWidgets import (
    QApplication,
    QFrame,
    QHBoxLayout,
    QLabel,
    QMenu,
    QToolButton,
    QVBoxLayout,
)

from ..theme import GRID_SIZES
from .constants import BLOCK_MIME
from .robot_list import RobotList

# 3 linhas de ícones grandes + folga para o indicador de drop.
_THREE_ROWS_HEIGHT = GRID_SIZES["large"][1] * 3 + 24


class _DragHandle(QLabel):
    """Alça que inicia o arrasto do bloco (QDrag com BLOCK_MIME)."""

    def __init__(self, block_id: int):
        super().__init__("⠿")
        self.block_id = block_id
        self.setObjectName("BlockHandle")
        self.setCursor(Qt.OpenHandCursor)
        self.setToolTip("Arraste para reordenar o bloco")
        self._press_pos = None

    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            self._press_pos = event.position().toPoint()

    def mouseMoveEvent(self, event):
        if self._press_pos is None:
            return
        moved = (event.position().toPoint() - self._press_pos).manhattanLength()
        if moved < QApplication.startDragDistance():
            return
        drag = QDrag(self)
        mime = QMimeData()
        mime.setData(BLOCK_MIME, str(self.block_id).encode("utf-8"))
        drag.setMimeData(mime)
        drag.exec(Qt.MoveAction)
        self._press_pos = None

    def mouseReleaseEvent(self, event):
        self._press_pos = None


class BlockWidget(QFrame):
    addRobotRequested = Signal(int)     # block_id
    renameRequested = Signal(int)
    describeRequested = Signal(int)
    deleteRequested = Signal(int)
    moveToScreenRequested = Signal(int)
    moveUpRequested = Signal(int)
    moveDownRequested = Signal(int)

    def __init__(self, block, theme_name: str, parent=None):
        super().__init__(parent)
        self.block = block
        self.setObjectName("BlockCard")
        self.setFrameShape(QFrame.NoFrame)

        root = QVBoxLayout(self)
        root.setContentsMargins(14, 12, 14, 14)
        root.setSpacing(8)

        # ---- Cabeçalho ----
        header = QHBoxLayout()
        header.setSpacing(8)

        header.addWidget(_DragHandle(block.id))

        title_box = QVBoxLayout()
        title_box.setSpacing(0)
        self.title_label = QLabel(block.name)
        self.title_label.setObjectName("BlockTitle")
        self.title_label.setWordWrap(True)
        self.desc_label = QLabel(block.description or "Sem descrição")
        self.desc_label.setObjectName("BlockDesc")
        self.desc_label.setWordWrap(True)
        title_box.addWidget(self.title_label)
        title_box.addWidget(self.desc_label)
        header.addLayout(title_box)
        header.addStretch(1)

        add_btn = QToolButton()
        add_btn.setText("➕ Robô")
        add_btn.setToolTip("Adicionar robô neste bloco")
        add_btn.clicked.connect(lambda: self.addRobotRequested.emit(self.block.id))
        header.addWidget(add_btn)

        menu_btn = QToolButton()
        menu_btn.setText("⋯")
        menu_btn.setToolTip("Opções do bloco")
        menu_btn.setPopupMode(QToolButton.InstantPopup)
        menu_btn.setMenu(self._build_menu())
        header.addWidget(menu_btn)

        root.addLayout(header)

        # ---- Grade de robôs ----
        self.robot_list = RobotList(block.id, theme_name)
        self.robot_list.setMinimumHeight(_THREE_ROWS_HEIGHT)
        root.addWidget(self.robot_list)

    def _build_menu(self) -> QMenu:
        menu = QMenu(self)
        menu.addAction("✎  Renomear bloco", lambda: self.renameRequested.emit(self.block.id))
        menu.addAction("📝  Editar descrição", lambda: self.describeRequested.emit(self.block.id))
        menu.addSeparator()
        menu.addAction("⬆  Mover para cima", lambda: self.moveUpRequested.emit(self.block.id))
        menu.addAction("⬇  Mover para baixo", lambda: self.moveDownRequested.emit(self.block.id))
        menu.addAction("➦  Mover para outra tela…", lambda: self.moveToScreenRequested.emit(self.block.id))
        menu.addSeparator()
        menu.addAction("🗑  Excluir bloco", lambda: self.deleteRequested.emit(self.block.id))
        return menu

    def populate(self, robots) -> None:
        self.robot_list.clear()
        for robot in robots:
            self.robot_list.add_robot(robot)
