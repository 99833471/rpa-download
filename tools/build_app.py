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
- Feche o programa e de duplo-clique em "atualizar.bat".

Voce NAO precisa instalar Python nem nada alem disto.
"""


def build() -> int:
    recorder_js = os.path.join(ROOT, "app", "recorder", "recorder.js")
    args = [
        sys.executable, "-m", "PyInstaller",
        "--noconfirm", "--windowed",
        "--name", APP_NAME,
        "--collect-all", "playwright",
        "--collect-submodules", "app",
        "--collect-all", "holidays",
        "--add-data", f"{recorder_js}{os.pathsep}app/recorder",
        "--distpath", DIST,
        "--workpath", os.path.join(ROOT, "build", "work"),
        "--specpath", os.path.join(ROOT, "build"),
        os.path.join(ROOT, "main.py"),
    ]
    print("Executando PyInstaller…")
    return subprocess.run(args, cwd=ROOT).returncode


def package() -> int:
    if not os.path.isdir(APP_DIR):
        print("Pasta do app não encontrada:", APP_DIR)
        return 1
    # Auto-atualizador (versão .exe) + LEIAME dentro da pasta distribuída.
    shutil.copyfile(os.path.join(ROOT, "tools", "dist_atualizar.bat"),
                    os.path.join(APP_DIR, "atualizar.bat"))
    shutil.copyfile(os.path.join(ROOT, "tools", "dist_update.ps1"),
                    os.path.join(APP_DIR, "_update.ps1"))
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
    if "--repack" not in sys.argv:
        rc = build()
        if rc != 0:
            print("PyInstaller falhou.")
            return rc
    return package()


if __name__ == "__main__":
    sys.exit(main())
