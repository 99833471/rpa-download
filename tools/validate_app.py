"""Valida o app empacotado (.exe): o subprocesso de execução (despachante) e o
boot da GUI (offscreen, sem tocar na config real do usuário).

Uso:  .venv\\Scripts\\python tools\\validate_app.py
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
import time

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
APP_NAME = "RPA Download"
# Caminho do .exe: argumento opcional, senão o build em pasta (onedir).
EXE = (sys.argv[1] if len(sys.argv) > 1
       else os.path.join(ROOT, "dist", APP_NAME, APP_NAME + ".exe"))

_failures = []


def check(label, cond):
    print(f"  [{'OK ' if cond else 'FALHOU'}] {label}", flush=True)
    if not cond:
        _failures.append(label)


def test_executor_dispatch(work):
    print("== Subprocesso de execução (exe --rpa-exec) ==", flush=True)
    page = os.path.join(work, "page.html")
    with open(page, "w", encoding="utf-8") as f:
        f.write('<input id="data" name="data">'
                '<a id="dl" href="data:text/csv,a,b%0A1,2" download="relatorio.csv">Baixar</a>')
    url = "file:///" + page.replace("\\", "/")
    manifest = {
        "schema_version": 1, "name": "t", "start_url": url, "has_login": False,
        "session_file": "", "site_limit": {"enabled": False},
        "steps": [
            {"action": "goto", "url": url, "selectors": []},
            {"action": "fill", "selectors": [{"type": "id", "value": "#data"}],
             "field": {"type": "fixed", "value": "01/06/2026", "fmt": "dd/mm/yyyy"}},
            {"action": "click", "selectors": [{"type": "id", "value": "#dl"}]},
            {"action": "download", "selectors": []},
        ],
    }
    mpath = os.path.join(work, "robot.json")
    with open(mpath, "w", encoding="utf-8") as f:
        json.dump(manifest, f)
    out = os.path.join(work, "out")
    log = os.path.join(work, "run.log")
    rp = subprocess.run(
        [EXE, "--rpa-exec", "--manifest", mpath, "--download-dir", out, "--log", log],
        stdin=subprocess.DEVNULL, capture_output=True, text=True,
        encoding="utf-8", errors="replace", timeout=240,
    )
    check("exe --rpa-exec saiu com código 0", rp.returncode == 0)
    files = os.listdir(out) if os.path.isdir(out) else []
    check("o exe baixou um arquivo", len(files) == 1)
    if rp.returncode != 0:
        print(rp.stdout[-800:]); print(rp.stderr[-400:])


def test_gui_boot(work):
    print("== Boot da GUI (offscreen) ==", flush=True)
    cfg_dir = os.path.join(work, "cfg")
    data_root = os.path.join(work, "data", APP_NAME)
    os.makedirs(cfg_dir, exist_ok=True)
    os.makedirs(data_root, exist_ok=True)
    with open(os.path.join(cfg_dir, "config.json"), "w", encoding="utf-8") as f:
        json.dump({"data_root": data_root, "theme": "dark"}, f)

    env = dict(os.environ)
    env["QT_QPA_PLATFORM"] = "offscreen"
    env["RPA_CONFIG_DIR"] = cfg_dir
    env["RPA_DATA_ROOT"] = data_root  # local fixo p/ a pasta de dados (sem migrar)
    env["RPA_NO_SHORTCUTS"] = "1"  # não criar atalhos nem auto-instalar na validação
    proc = subprocess.Popen([EXE], env=env,
                            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    # onefile descomprime a cada início; dá mais tempo quando necessário.
    time.sleep(int(os.environ.get("RPA_BOOT_WAIT", "12")))
    alive = proc.poll() is None
    check("a GUI iniciou e seguiu rodando (não crashou)", alive)
    check("criou o banco em data_root/.rpa", os.path.isfile(os.path.join(data_root, ".rpa", "app.db")))
    if alive:
        proc.terminate()
        try:
            proc.wait(timeout=10)
        except subprocess.TimeoutExpired:
            proc.kill()
        time.sleep(1.5)  # dá tempo de liberar o handle do banco (WAL)


def main():
    if not os.path.isfile(EXE):
        print("EXE não encontrado:", EXE)
        return 1
    print("EXE:", EXE)
    with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as work:
        test_executor_dispatch(work)
        test_gui_boot(work)
    print()
    if _failures:
        print(f"RESULTADO: {len(_failures)} falha(s): {_failures}")
        return 1
    print("RESULTADO: app empacotado - OK")
    return 0


if __name__ == "__main__":
    sys.exit(main())
