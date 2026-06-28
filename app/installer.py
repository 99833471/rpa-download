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
import shutil
import subprocess
import sys

from . import config

# Marcador que identifica uma pasta de extração (_MEI*) como DESTE app — evita
# tocar nas sobras de outros programas PyInstaller.
_OUR_MARKER = os.path.join("app", "recorder", "recorder.js")

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


def purge_stale_runtime_dirs(parent: str, current: str) -> int:
    """Remove pastas `_MEI*` deixadas por execuções anteriores DESTE app.

    Só apaga pastas que (a) têm o nosso marcador e (b) **não estão em uso**: tenta
    renomear antes de apagar — no Windows, renomear uma pasta com arquivos abertos
    falha, então uma instância viva (outra janela, subprocesso de execução) nunca é
    tocada. Pastas de outros programas PyInstaller são ignoradas. Best-effort.
    """
    removed = 0
    try:
        names = os.listdir(parent)
    except OSError:
        return 0
    cur_norm = os.path.normcase(os.path.normpath(current)) if current else ""
    for name in names:
        if not name.startswith("_MEI"):
            continue
        path = os.path.join(parent, name)
        if not os.path.isdir(path):
            continue
        if cur_norm and os.path.normcase(os.path.normpath(path)) == cur_norm:
            continue  # a pasta da instância atual
        if not os.path.isfile(os.path.join(path, _OUR_MARKER)):
            continue  # não é nossa
        tmp = path + ".del"
        try:
            os.rename(path, tmp)  # falha se estiver em uso (handles abertos)
        except OSError:
            continue  # em uso por outra instância → deixa quieto
        shutil.rmtree(tmp, ignore_errors=True)
        removed += 1
    return removed


def cleanup_stale_runtime_dirs() -> int:
    """Limpa sobras `_MEI*` no diretório de extração (faz sentido só no .exe)."""
    if not getattr(sys, "frozen", False):
        return 0
    base = getattr(sys, "_MEIPASS", None)
    if not base:
        return 0
    return purge_stale_runtime_dirs(os.path.dirname(base), base)
