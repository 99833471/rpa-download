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
APP_NAME = "RPA Download"
ICON = os.path.join(ROOT, "app", "assets", "icon.ico")

# Saída do build. Pode ser redirecionada para FORA do OneDrive (que costuma
# travar arquivos durante o build) via as variáveis RPA_DIST / RPA_WORK.
DIST = os.environ.get("RPA_DIST", os.path.join(ROOT, "dist"))
BUILD = os.environ.get("RPA_WORK", os.path.join(ROOT, "build"))
APP_DIR = os.path.join(DIST, APP_NAME)

_LEIAME = """RPA DOWNLOAD

COMO USAR
1. Extraia esta pasta inteira para um local fixo (ex.: C:\\RPA-DOWNLOAD).
2. Abra "RPA Download.exe".
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


def _read_version():
    init = os.path.join(ROOT, "app", "__init__.py")
    try:
        for line in open(init, encoding="utf-8"):
            if line.strip().startswith("__version__"):
                return line.split("=", 1)[1].strip().strip('"').strip("'")
    except OSError:
        pass
    return "1.0.0"


def _version_file():
    """Gera o arquivo de metadados (VS_VERSIONINFO) do .exe — reduz falso positivo
    de antivírus, pois um executável 'anônimo' é mais suspeito."""
    version = _read_version()
    a, b, c, d = (int(x) for x in (version.split(".") + ["0", "0", "0", "0"])[:4])
    os.makedirs(BUILD, exist_ok=True)
    path = os.path.join(BUILD, "version_info.txt")
    content = f"""# UTF-8
VSVersionInfo(
  ffi=FixedFileInfo(
    filevers=({a}, {b}, {c}, {d}), prodvers=({a}, {b}, {c}, {d}),
    mask=0x3f, flags=0x0, OS=0x40004, fileType=0x1, subtype=0x0, date=(0, 0)),
  kids=[
    StringFileInfo([StringTable('040904B0', [
      StringStruct('CompanyName', 'Anheuser-Busch InBev'),
      StringStruct('FileDescription', 'RPA Download - automatizador de downloads'),
      StringStruct('FileVersion', '{version}'),
      StringStruct('InternalName', 'RPA Download'),
      StringStruct('OriginalFilename', 'RPA Download.exe'),
      StringStruct('ProductName', 'RPA Download'),
      StringStruct('ProductVersion', '{version}')])]),
    VarFileInfo([VarStruct('Translation', [1033, 1200])])])
"""
    with open(path, "w", encoding="utf-8") as f:
        f.write(content)
    return path


def _common_args(recorder_js):
    return [
        sys.executable, "-m", "PyInstaller",
        "--noconfirm", "--windowed", "--noupx",
        "--name", APP_NAME,
        "--icon", ICON,
        "--version-file", _version_file(),
        "--collect-all", "playwright",
        "--collect-submodules", "app",
        "--collect-all", "holidays",
        "--add-data", f"{recorder_js}{os.pathsep}app/recorder",
        "--add-data", f"{ICON}{os.pathsep}app/assets",
    ]


def build() -> int:
    """Build em modo PASTA (onedir) — abre rápido; distribuído como .zip."""
    recorder_js = os.path.join(ROOT, "app", "recorder", "recorder.js")
    args = _common_args(recorder_js) + [
        "--distpath", DIST,
        "--workpath", os.path.join(BUILD, "work"),
        "--specpath", BUILD,
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
        "--workpath", os.path.join(BUILD, "work_onefile"),
        "--specpath", os.path.join(BUILD, "onefile"),
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
