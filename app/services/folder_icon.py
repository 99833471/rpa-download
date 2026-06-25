"""Aplica um ícone personalizado à pasta de dados no Windows Explorer.

Usa o mecanismo nativo do Windows: um desktop.ini apontando para um .ico, com os
atributos de arquivo adequados. Falhas são silenciosas (não derrubam o app).
"""

from __future__ import annotations

import ctypes
import os
import shutil

_FILE_ATTRIBUTE_READONLY = 0x01
_FILE_ATTRIBUTE_HIDDEN = 0x02
_FILE_ATTRIBUTE_SYSTEM = 0x04

_DESKTOP_INI = (
    "[.ShellClassInfo]\r\n"
    "IconResource=.rpa\\folder.ico,0\r\n"
    "ConfirmFileOp=0\r\n"
    "[ViewState]\r\n"
    "Mode=\r\n"
    "Vid=\r\n"
    "FolderType=Generic\r\n"
)


def set_folder_icon(folder: str, src_ico: str) -> None:
    if os.name != "nt" or not folder or not os.path.isdir(folder) or not os.path.isfile(src_ico):
        return
    try:
        rpa = os.path.join(folder, ".rpa")
        os.makedirs(rpa, exist_ok=True)
        dst_ico = os.path.join(rpa, "folder.ico")
        if (not os.path.isfile(dst_ico)
                or os.path.getsize(dst_ico) != os.path.getsize(src_ico)):
            shutil.copyfile(src_ico, dst_ico)

        ini = os.path.join(folder, "desktop.ini")
        with open(ini, "w", encoding="utf-8") as f:
            f.write(_DESKTOP_INI)

        set_attr = ctypes.windll.kernel32.SetFileAttributesW
        # desktop.ini precisa ser oculto + sistema; a pasta precisa de readonly/system
        # para o Explorer aplicar o ícone personalizado.
        set_attr(str(ini), _FILE_ATTRIBUTE_HIDDEN | _FILE_ATTRIBUTE_SYSTEM)
        set_attr(str(dst_ico), _FILE_ATTRIBUTE_HIDDEN)
        set_attr(str(folder), _FILE_ATTRIBUTE_READONLY)
    except Exception:
        pass
