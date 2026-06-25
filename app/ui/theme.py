"""Temas Light/Dark e geração de ícones de robô.

- Light Mode: azul e branco (inspiração Ambev).
- Dark Mode:  preto e dourado (inspiração AB InBev).
"""

from __future__ import annotations

from PySide6.QtCore import QRectF, Qt
from PySide6.QtGui import QBrush, QColor, QFont, QIcon, QPainter, QPen, QPixmap

PALETTES = {
    "light": {
        "bg": "#EEF3FA",
        "surface": "#FFFFFF",
        "surface_alt": "#F4F7FC",
        "primary": "#0A4DA2",
        "accent": "#1769E0",
        "text": "#0B2545",
        "subtext": "#5A6B85",
        "border": "#D2DEEF",
        "hover": "#E3ECFA",
        "icon_bg": "#FFFFFF",
        "icon_fg": "#0A4DA2",
        "danger": "#C0392B",
    },
    "dark": {
        "bg": "#0C0C0E",
        "surface": "#161619",
        "surface_alt": "#1E1E22",
        "primary": "#D4AF37",
        "accent": "#E8C766",
        "text": "#F2E9CE",
        "subtext": "#9C9684",
        "border": "#2C2C31",
        "hover": "#23231f",
        "icon_bg": "#1F1F23",
        "icon_fg": "#D4AF37",
        "danger": "#E06C6C",
    },
}


def get_palette(name: str) -> dict:
    return PALETTES.get(name, PALETTES["dark"])


def build_qss(name: str) -> str:
    p = get_palette(name)
    return f"""
    QWidget {{
        background-color: {p['bg']};
        color: {p['text']};
        font-family: 'Segoe UI', Arial, sans-serif;
        font-size: 13px;
    }}
    QMainWindow, QDialog {{ background-color: {p['bg']}; }}

    /* Barra de ferramentas superior */
    #TopBar {{
        background-color: {p['surface']};
        border-bottom: 1px solid {p['border']};
    }}
    #AppTitle {{ font-size: 16px; font-weight: 700; color: {p['primary']}; }}
    #AppSubtitle {{ color: {p['subtext']}; font-size: 11px; }}

    /* Botões */
    QPushButton {{
        background-color: {p['surface_alt']};
        color: {p['text']};
        border: 1px solid {p['border']};
        border-radius: 8px;
        padding: 6px 14px;
    }}
    QPushButton:hover {{ background-color: {p['hover']}; border-color: {p['primary']}; }}
    QPushButton:pressed {{ background-color: {p['primary']}; color: {p['surface']}; }}
    QPushButton#Primary {{
        background-color: {p['primary']};
        color: {p['surface']};
        border: none;
        font-weight: 600;
    }}
    QPushButton#Primary:hover {{ background-color: {p['accent']}; }}
    QToolButton {{
        background-color: transparent;
        border: 1px solid transparent;
        border-radius: 8px;
        padding: 4px 10px;
        color: {p['text']};
    }}
    QToolButton:hover {{ background-color: {p['hover']}; border-color: {p['border']}; }}

    /* Abas das Telas */
    QTabWidget::pane {{ border: none; background: {p['bg']}; }}
    QTabBar::tab {{
        background: {p['surface_alt']};
        color: {p['subtext']};
        border: 1px solid {p['border']};
        border-bottom: none;
        border-top-left-radius: 10px;
        border-top-right-radius: 10px;
        padding: 8px 18px;
        margin-right: 4px;
        font-weight: 600;
    }}
    QTabBar::tab:selected {{
        background: {p['surface']};
        color: {p['primary']};
        border-color: {p['primary']};
    }}
    QTabBar::tab:hover {{ color: {p['text']}; }}

    /* Cartão de Bloco */
    #BlockCard {{
        background-color: {p['surface']};
        border: 1px solid {p['border']};
        border-radius: 14px;
    }}
    #BlockTitle {{ font-size: 15px; font-weight: 700; color: {p['text']}; }}
    #BlockDesc {{ color: {p['subtext']}; font-size: 11px; }}
    #BlockHandle {{ color: {p['subtext']}; font-size: 18px; }}

    /* Lista de robôs (ícones) */
    QListWidget {{
        background-color: {p['surface_alt']};
        border: 1px dashed {p['border']};
        border-radius: 10px;
        padding: 6px;
    }}
    QListWidget::item {{
        color: {p['text']};
        border-radius: 8px;
        padding: 6px 2px;
    }}
    QListWidget::item:selected {{ background-color: {p['hover']}; color: {p['text']}; }}
    QListWidget::item:hover {{ background-color: {p['hover']}; }}

    /* Inputs */
    QLineEdit, QTextEdit, QComboBox {{
        background-color: {p['surface']};
        border: 1px solid {p['border']};
        border-radius: 8px;
        padding: 6px 8px;
        selection-background-color: {p['accent']};
    }}
    QLineEdit:focus, QTextEdit:focus, QComboBox:focus {{ border-color: {p['primary']}; }}

    /* Menus */
    QMenu {{
        background-color: {p['surface']};
        border: 1px solid {p['border']};
        border-radius: 8px;
        padding: 4px;
    }}
    QMenu::item {{ padding: 6px 22px; border-radius: 6px; }}
    QMenu::item:selected {{ background-color: {p['primary']}; color: {p['surface']}; }}
    QMenu::separator {{ height: 1px; background: {p['border']}; margin: 4px 6px; }}

    /* Scrollbars */
    QScrollBar:vertical {{ background: transparent; width: 10px; margin: 2px; }}
    QScrollBar::handle:vertical {{ background: {p['border']}; border-radius: 5px; min-height: 30px; }}
    QScrollBar::handle:vertical:hover {{ background: {p['primary']}; }}
    QScrollBar::add-line, QScrollBar::sub-line {{ height: 0; }}
    QScrollBar:horizontal {{ background: transparent; height: 10px; margin: 2px; }}
    QScrollBar::handle:horizontal {{ background: {p['border']}; border-radius: 5px; min-width: 30px; }}
    QScrollBar::handle:horizontal:hover {{ background: {p['primary']}; }}

    #StatusBar {{ color: {p['subtext']}; font-size: 11px; }}
    """


# Tamanhos dos ícones de robô (px do desenho) e largura/altura-base da célula.
# A altura real de cada célula é calculada para caber o nome completo (RobotList).
ICON_SIZES = {"large": 72, "small": 48}
GRID_SIZES = {"large": (150, 132), "small": (108, 104)}


def make_robot_icon(name: str, size_key: str, theme_name: str) -> QIcon:
    """Gera dinamicamente um ícone quadrado arredondado com as iniciais do robô."""
    pal = get_palette(theme_name)
    px = ICON_SIZES.get(size_key, ICON_SIZES["large"])

    pm = QPixmap(px, px)
    pm.fill(Qt.transparent)
    painter = QPainter(pm)
    painter.setRenderHint(QPainter.Antialiasing)

    rect = QRectF(2, 2, px - 4, px - 4)
    radius = px * 0.20
    painter.setBrush(QBrush(QColor(pal["icon_bg"])))
    painter.setPen(QPen(QColor(pal["icon_fg"]), 2))
    painter.drawRoundedRect(rect, radius, radius)

    initials = "".join(w[0] for w in name.split()[:2]).upper() or "?"
    font = QFont("Segoe UI", int(px * 0.30))
    font.setBold(True)
    painter.setFont(font)
    painter.setPen(QColor(pal["icon_fg"]))
    painter.drawText(rect, Qt.AlignCenter, initials)
    painter.end()

    return QIcon(pm)
