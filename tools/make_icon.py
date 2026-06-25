"""Gera o ícone do programa em app/assets/icon.ico (multi-resolução).

Desenha um quadrado escuro arredondado com uma seta de download dourada (tema do
app). Rode uma vez:  .venv\\Scripts\\python tools\\make_icon.py
"""

from __future__ import annotations

import os
import struct
import sys

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtCore import QBuffer, QByteArray, QPointF, QRectF, Qt  # noqa: E402
from PySide6.QtGui import (  # noqa: E402
    QBrush, QColor, QGuiApplication, QImage, QPainter, QPen, QPolygonF,
)

SIZES = [16, 32, 48, 64, 128, 256]


def render(s: int) -> QImage:
    img = QImage(s, s, QImage.Format_ARGB32)
    img.fill(Qt.transparent)
    p = QPainter(img)
    p.setRenderHint(QPainter.Antialiasing)

    margin = s * 0.06
    rect = QRectF(margin, margin, s - 2 * margin, s - 2 * margin)
    radius = s * 0.22
    p.setBrush(QBrush(QColor("#161619")))
    p.setPen(QPen(QColor("#D4AF37"), max(1.0, s * 0.045)))
    p.drawRoundedRect(rect, radius, radius)

    cx = s / 2.0
    p.setPen(Qt.NoPen)
    p.setBrush(QBrush(QColor("#D4AF37")))

    # Haste da seta.
    shaft_w = s * 0.12
    p.drawRoundedRect(QRectF(cx - shaft_w / 2, s * 0.24, shaft_w, s * 0.28),
                      shaft_w * 0.4, shaft_w * 0.4)
    # Ponta da seta (triângulo para baixo).
    head = QPolygonF([QPointF(cx - s * 0.19, s * 0.50),
                      QPointF(cx + s * 0.19, s * 0.50),
                      QPointF(cx, s * 0.72)])
    p.drawPolygon(head)
    # Base/bandeja.
    base_w, base_h = s * 0.48, s * 0.085
    p.drawRoundedRect(QRectF(cx - base_w / 2, s * 0.76, base_w, base_h),
                      base_h * 0.4, base_h * 0.4)
    p.end()
    return img


def png_bytes(img: QImage) -> bytes:
    ba = QByteArray()
    buf = QBuffer(ba)
    buf.open(QBuffer.WriteOnly)
    img.save(buf, "PNG")
    buf.close()
    return bytes(ba)


def build_ico(path: str) -> None:
    imgs = [(s, png_bytes(render(s))) for s in SIZES]
    n = len(imgs)
    out = struct.pack("<HHH", 0, 1, n)  # ICONDIR
    offset = 6 + 16 * n
    entries = b""
    datas = b""
    for s, data in imgs:
        dim = 0 if s >= 256 else s
        entries += struct.pack("<BBBBHHII", dim, dim, 0, 0, 1, 32, len(data), offset)
        offset += len(data)
        datas += data
    with open(path, "wb") as f:
        f.write(out + entries + datas)


def main() -> int:
    QGuiApplication(sys.argv)
    root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    out = os.path.join(root, "app", "assets", "icon.ico")
    os.makedirs(os.path.dirname(out), exist_ok=True)
    build_ico(out)
    print("Ícone gerado:", out, f"({os.path.getsize(out)} bytes)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
