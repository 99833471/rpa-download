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
    """Se estiver rodando fora do local canônico, copia a PASTA do app para lá e
    reabre de lá.

    A distribuição é em **modo pasta** (onedir): "o programa" é a pasta que contém
    o .exe + `_internal`. Copiamos a pasta inteira para
    %LOCALAPPDATA%\\Programs\\RPA Download e reabrimos o .exe instalado.

    Retorna True quando reabriu a cópia instalada (o chamador deve encerrar este
    processo); False quando já está instalado ou não há o que fazer.
    """
    if os.name != "nt" or not getattr(sys, "frozen", False):
        return False
    if os.environ.get("RPA_NO_SHORTCUTS"):  # validação/teste: não auto-instala
        return False

    try:
        current_exe = os.path.realpath(sys.executable)
        current_dir = os.path.dirname(current_exe)
        target_dir = os.path.realpath(config.install_dir())
        target_exe = os.path.join(target_dir, os.path.basename(current_exe))
    except OSError:
        return False
    if _same(current_dir, target_dir):
        return False  # já está rodando do local instalado

    try:
        os.makedirs(os.path.dirname(target_dir), exist_ok=True)
        shutil.copytree(current_dir, target_dir, dirs_exist_ok=True)
    except OSError:
        return False  # não conseguiu instalar (ex.: arquivo em uso) → roda no lugar

    try:
        subprocess.Popen(
            [target_exe],
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
    """Limpa sobras `_MEI*` deixadas por execuções anteriores.

    Varre o diretório de extração atual e também o `%TEMP%` (onde o antigo modo
    onefile extraía), para remover sobras herdadas. Só no .exe; best-effort.
    """
    if not getattr(sys, "frozen", False):
        return 0
    import tempfile
    base = getattr(sys, "_MEIPASS", "") or ""
    parents = set()
    if base:
        parents.add(os.path.dirname(base))
    parents.add(tempfile.gettempdir())
    removed = 0
    for parent in parents:
        removed += purge_stale_runtime_dirs(parent, base)
    return removed
