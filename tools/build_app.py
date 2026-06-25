"""Empacota o AUTOMATIZADOR como aplicativo standalone (PyInstaller, modo pasta).

Gera dist/<NOME>/ (com o .exe), inclui o auto-atualizador e um LEIAME, e cria um
.zip pronto para distribuir. O usuário final NÃO precisa de Python; o navegador
(Chromium) é baixado no primeiro uso.

Uso:
    .venv\\Scripts\\python tools\\build_app.py            (build completo + zip)
    .venv\\Scripts\\python tools\\build_app.py --repack    (só reempacota o que já foi buildado)
"""

from __future__ import annotations

import os
import shutil
import subprocess
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
APP_NAME = "AUTOMATIZADOR DOWNLOAD DE DADOS"
DIST = os.path.join(ROOT, "dist")
APP_DIR = os.path.join(DIST, APP_NAME)

_LEIAME = """AUTOMATIZADOR DOWNLOAD DE DADOS

COMO USAR
1. Extraia esta pasta inteira para um local fixo (ex.: C:\\AUTOMATIZADOR).
2. Abra "AUTOMATIZADOR DOWNLOAD DE DADOS.exe".
3. Na primeira vez, escolha uma pasta raiz onde os dados serao guardados.

Observacao: na primeira vez que um robo for executado, o navegador (Chromium)
e baixado automaticamente (precisa de internet uma unica vez).

ATUALIZAR PARA A VERSAO MAIS RECENTE
Peca a versao mais recente (arquivo .zip) a quem lhe enviou o programa,
extraia e substitua esta pasta.

Voce NAO precisa instalar Python nem nada alem disto.
"""


ONEFILE_DIST = os.path.join(DIST, "onefile")
ONEFILE_EXE = os.path.join(ONEFILE_DIST, APP_NAME + ".exe")


def _common_args(recorder_js):
    return [
        sys.executable, "-m", "PyInstaller",
        "--noconfirm", "--windowed",
        "--name", APP_NAME,
        "--collect-all", "playwright",
        "--collect-submodules", "app",
        "--collect-all", "holidays",
        "--add-data", f"{recorder_js}{os.pathsep}app/recorder",
    ]


def build() -> int:
    """Build em modo PASTA (onedir) — abre rápido; distribuído como .zip."""
    recorder_js = os.path.join(ROOT, "app", "recorder", "recorder.js")
    args = _common_args(recorder_js) + [
        "--distpath", DIST,
        "--workpath", os.path.join(ROOT, "build", "work"),
        "--specpath", os.path.join(ROOT, "build"),
        os.path.join(ROOT, "main.py"),
    ]
    print("PyInstaller (modo pasta)…")
    return subprocess.run(args, cwd=ROOT).returncode


def build_onefile() -> int:
    """Build em ARQUIVO ÚNICO (onefile) — um só .exe pronto para uso."""
    recorder_js = os.path.join(ROOT, "app", "recorder", "recorder.js")
    args = _common_args(recorder_js) + [
        "--onefile",
        "--distpath", ONEFILE_DIST,
        "--workpath", os.path.join(ROOT, "build", "work_onefile"),
        "--specpath", os.path.join(ROOT, "build", "onefile"),
        os.path.join(ROOT, "main.py"),
    ]
    print("PyInstaller (arquivo único)…")
    rc = subprocess.run(args, cwd=ROOT).returncode
    if rc == 0:
        print("EXE único:", ONEFILE_EXE)
    return rc


def package() -> int:
    if not os.path.isdir(APP_DIR):
        print("Pasta do app não encontrada:", APP_DIR)
        return 1
    # Remove eventuais atualizadores antigos (não se aplicam à distribuição
    # manual de repositório privado).
    for stale in ("atualizar.bat", "_update.ps1"):
        p = os.path.join(APP_DIR, stale)
        if os.path.isfile(p):
            os.remove(p)
    with open(os.path.join(APP_DIR, "LEIAME.txt"), "w", encoding="utf-8") as f:
        f.write(_LEIAME)

    zip_base = os.path.join(DIST, APP_NAME.replace(" ", "_"))
    if os.path.isfile(zip_base + ".zip"):
        os.remove(zip_base + ".zip")
    print("Compactando em .zip…")
    shutil.make_archive(zip_base, "zip", DIST, APP_NAME)

    print("OK")
    print("EXE:", os.path.join(APP_DIR, APP_NAME + ".exe"))
    print("ZIP:", zip_base + ".zip")
    return 0


def main() -> int:
    if "--repack" in sys.argv:
        return package()
    if "--onefile-only" in sys.argv:
        return build_onefile()
    rc = build()
    if rc != 0:
        print("PyInstaller falhou (modo pasta).")
        return rc
    rc = package()
    if rc != 0:
        return rc
    rc = build_onefile()
    if rc != 0:
        print("PyInstaller falhou (arquivo único).")
    return rc


if __name__ == "__main__":
    sys.exit(main())
