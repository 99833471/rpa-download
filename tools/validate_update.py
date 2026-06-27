"""Valida o fluxo de auto-atualização (pós-migração para victoraalm), sem mexer no
app instalado:
  1. Detecção da release pela API no caminho NOVO (victoraalm) e no ANTIGO
     (99833471, que deve redirecionar) — prova que instalações antigas atualizam.
  2. Comparação de versões (is_newer).
  3. O asset publicado é um .exe válido (cabeçalho MZ) e tem tamanho.
  4. Mecanismo de troca do .exe (o .bat) num sandbox isolado: espera o processo
     fechar -> move o novo sobre o antigo -> reabre -> se autoexclui.

Uso:  python tools/validate_update.py
"""

from __future__ import annotations

import os
import shutil
import subprocess
import sys
import tempfile
import time
import urllib.request

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app import updater  # noqa: E402
from app.ui.update_controller import build_update_bat  # noqa: E402

_failures = []


def check(label, cond):
    print(f"  [{'OK ' if cond else 'FALHOU'}] {label}", flush=True)
    if not cond:
        _failures.append(label)


def _latest_tag(url):
    req = urllib.request.Request(url, headers={
        "User-Agent": "rpa-updater", "Accept": "application/vnd.github+json"})
    import json
    with urllib.request.urlopen(req, timeout=15) as r:
        return json.load(r)


def test_detection():
    print("== Detecção da release (API) ==")
    new = updater.fetch_latest()
    check("caminho NOVO (victoraalm) responde", new is not None and bool(new.get("tag")))
    if new:
        print("   última versão:", new["tag"], "| asset:", new["asset_name"])
        check("asset é um .exe", new["asset_name"].lower().endswith(".exe"))
    # caminho antigo deve redirecionar (301) e devolver a MESMA release
    try:
        old = _latest_tag("https://api.github.com/repos/99833471/rpa-download/releases/latest")
        check("caminho ANTIGO (99833471) redireciona e devolve release", bool(old.get("tag_name")))
        check("redirect aponta para a mesma versão do novo",
              new is not None and old.get("tag_name") == new["tag"])
    except Exception as e:  # noqa: BLE001
        check(f"caminho antigo redireciona ({e})", False)
    return new


def test_is_newer():
    print("== Comparação de versões ==")
    check("1.5.1 > 1.5.0", updater.is_newer("v1.5.1", "1.5.0") is True)
    check("1.5.1 == 1.5.1 (não atualiza)", updater.is_newer("v1.5.1", "1.5.1") is False)
    check("1.5.0 < 1.5.1 (não 'newer')", updater.is_newer("v1.5.0", "1.5.1") is False)
    check("1.10.0 > 1.9.0", updater.is_newer("v1.10.0", "1.9.0") is True)


def test_asset(new):
    print("== Asset é um .exe válido ==")
    if not new or not new.get("asset_url"):
        check("asset disponível", False)
        return
    req = urllib.request.Request(new["asset_url"], headers={"User-Agent": "rpa-updater"})
    with urllib.request.urlopen(req, timeout=30) as r:
        head = r.read(2)
        size = int(r.headers.get("Content-Length", 0) or 0)
    check("começa com 'MZ' (executável Windows)", head == b"MZ")
    check("tamanho informado > 10 MB", size > 10 * 1024 * 1024)
    print(f"   asset: {size/1048576:.1f} MB")


def test_replace_mechanism():
    print("== Troca do .exe (sandbox isolado) ==")
    ping = shutil.which("ping") or r"C:\Windows\System32\ping.exe"
    sandbox = tempfile.mkdtemp(prefix="rpa_upd_")
    target = os.path.join(sandbox, "target.exe")   # 'app instalado'
    newexe = os.path.join(sandbox, "new.exe")       # 'atualização baixada'
    shutil.copyfile(ping, target)
    shutil.copyfile(ping, newexe)

    # processo 'rodando' com o mesmo nome do alvo (target.exe)
    blocker = subprocess.Popen([target, "-n", "600", "127.0.0.1"],
                               stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                               stdin=subprocess.DEVNULL)
    bat = os.path.join(sandbox, "upd.bat")
    with open(bat, "w", encoding="utf-8") as f:
        f.write(build_update_bat(target, newexe, "target.exe"))

    subprocess.Popen(["cmd", "/c", bat],
                     creationflags=0x08000000 | subprocess.CREATE_NEW_PROCESS_GROUP,  # CREATE_NO_WINDOW
                     close_fds=True)
    time.sleep(2.0)  # garante o .bat no laço de espera
    # ainda travado? new.exe deve continuar existindo enquanto o processo vive
    waiting_ok = os.path.exists(newexe)
    blocker.terminate()
    try:
        blocker.wait(timeout=5)
    except subprocess.TimeoutExpired:
        blocker.kill()

    deadline = time.time() + 40
    while time.time() < deadline and (os.path.exists(newexe) or os.path.exists(bat)):
        time.sleep(0.5)

    check("esperou enquanto o app estava aberto", waiting_ok)
    check("moveu a atualização sobre o executável (origem consumida)", not os.path.exists(newexe))
    check("executável final existe", os.path.exists(target))
    check("o .bat se autoexcluiu", not os.path.exists(bat))

    try:
        subprocess.run(["taskkill", "/IM", "target.exe", "/F", "/T"],
                       stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    except Exception:
        pass
    time.sleep(0.5)
    shutil.rmtree(sandbox, ignore_errors=True)


def main():
    new = test_detection()
    test_is_newer()
    test_asset(new)
    test_replace_mechanism()
    print()
    if _failures:
        print(f"RESULTADO: {len(_failures)} falha(s): {_failures}")
        return 1
    print("RESULTADO: fluxo de auto-atualização - OK")
    return 0


if __name__ == "__main__":
    sys.exit(main())
