"""Auto-instalação do executável (por usuário, sem admin).

Como apps profissionais por usuário (VS Code, GitHub Desktop…), o programa se
copia para %LOCALAPPDATA%\\Programs\\RPA Download na primeira execução e passa a
rodar de lá. Esse local é sempre gravável sem admin — o que também torna o
auto-atualizador mais confiável (ao contrário de Program Files / OneDrive).

Tudo é best-effort: se não conseguir instalar (ex.: cópia em uso), o programa
apenas roda de onde está.
"""

from __future__ import annotations

import os
import subprocess
import sys

from . import config

_DETACHED_PROCESS = 0x00000008
_CREATE_NEW_PROCESS_GROUP = 0x00000200


def installed_exe() -> str:
    """Caminho canônico do .exe instalado."""
    return os.path.join(config.install_dir(), config.APP_DISPLAY_NAME + ".exe")


def ensure_installed() -> bool:
    """Se estiver rodando fora do local canônico, copia-se para lá e reabre.

    Retorna True quando reabriu a cópia instalada (o chamador deve encerrar este
    processo); False quando já está instalado ou não há o que fazer.
    """
    if os.name != "nt" or not getattr(sys, "frozen", False):
        return False
    if os.environ.get("RPA_NO_SHORTCUTS"):  # validação/teste: não auto-instala
        return False

    try:
        current = os.path.realpath(sys.executable)
        target = os.path.realpath(installed_exe())
    except OSError:
        return False
    if _same(current, target):
        return False  # já está rodando do local instalado

    try:
        os.makedirs(os.path.dirname(target), exist_ok=True)
        # cópia em duas etapas (tmp + replace) para não deixar um .exe parcial
        tmp = target + ".new"
        import shutil
        shutil.copy2(current, tmp)
        os.replace(tmp, target)
    except OSError:
        return False  # não conseguiu instalar → roda no lugar

    try:
        subprocess.Popen(
            [target],
            creationflags=_DETACHED_PROCESS | _CREATE_NEW_PROCESS_GROUP,
            close_fds=True,
        )
    except OSError:
        return False
    return True


def _same(a: str, b: str) -> bool:
    return os.path.normcase(os.path.normpath(a)) == os.path.normcase(os.path.normpath(b))
