"""Valida o fluxo de auto-atualização (pós-migração para victoraalm), sem mexer no
app instalado:
  1. Detecção da release pela API no caminho NOVO (victoraalm) e no ANTIGO
     (99833471, que deve redirecionar) — prova que instalações antigas atualizam.
  2. Comparação de versões (is_newer).
  3. O asset publicado é um .exe válido (cabeçalho MZ) e tem tamanho.
  4. Mecanismo de troca da PASTA (via .zip) num sandbox isolado: espera o processo
     fechar (por PID) -> extrai o .zip -> substitui a pasta -> reabre -> autoexclui.

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
from app.ui.update_controller import build_update_zip_script  # noqa: E402

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
    print("== Troca da pasta via .zip (sandbox isolado, espera por PID) ==")
    ping = shutil.which("ping") or r"C:\Windows\System32\ping.exe"
    other = shutil.which("hostname") or r"C:\Windows\System32\hostname.exe"
    sandbox = tempfile.mkdtemp(prefix="rpa_upd_")

    # 'app instalado' (pasta) com um arquivo obsoleto que deve sumir na troca.
    installed = os.path.join(sandbox, "installed")
    os.makedirs(installed)
    inst_exe = os.path.join(installed, "RPA Download.exe")
    shutil.copyfile(ping, inst_exe)
    with open(os.path.join(installed, "old.txt"), "w") as f:
        f.write("OLD")

    # nova versão: pasta "RPA Download" compactada num .zip (como a release).
    newsrc = os.path.join(sandbox, "newsrc")
    newapp = os.path.join(newsrc, "RPA Download")
    os.makedirs(newapp)
    shutil.copyfile(other, os.path.join(newapp, "RPA Download.exe"))
    with open(os.path.join(newapp, "marker.txt"), "w") as f:
        f.write("NEW")
    zip_path = shutil.make_archive(os.path.join(sandbox, "update"), "zip", newsrc, "RPA Download")

    # processo 'rodando' a partir da pasta instalada — segura a pasta por PID.
    blocker = subprocess.Popen([inst_exe, "-n", "600", "127.0.0.1"],
                               stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                               stdin=subprocess.DEVNULL)
    extract = os.path.join(sandbox, "extract")
    script = os.path.join(sandbox, "upd.ps1")
    with open(script, "w", encoding="utf-8") as f:
        f.write(build_update_zip_script(blocker.pid, zip_path, extract, installed,
                                        inst_exe, "RPA Download", script))

    subprocess.Popen(["powershell", "-NoProfile", "-NonInteractive", "-ExecutionPolicy", "Bypass",
                      "-WindowStyle", "Hidden", "-File", script],
                     creationflags=0x08000000 | subprocess.CREATE_NEW_PROCESS_GROUP,  # CREATE_NO_WINDOW
                     close_fds=True)
    marker = os.path.join(installed, "marker.txt")
    old = os.path.join(installed, "old.txt")
    time.sleep(2.0)  # script deve estar esperando o PID (ainda não trocou)
    waiting_ok = (os.path.exists(old) and not os.path.exists(marker))
    blocker.terminate()
    try:
        blocker.wait(timeout=5)
    except subprocess.TimeoutExpired:
        blocker.kill()

    deadline = time.time() + 50
    replaced = False
    while time.time() < deadline:
        if os.path.exists(marker) and not os.path.exists(old) and not os.path.exists(script):
            replaced = True
            break
        time.sleep(0.5)

    check("esperou enquanto o app estava aberto (não trocou cedo)", waiting_ok)
    check("substituiu a pasta pela nova versão (marker presente)", os.path.exists(marker))
    check("removeu arquivos obsoletos da versão antiga (old.txt sumiu)", not os.path.exists(old))
    check("o script se autoexcluiu", not os.path.exists(script))

    time.sleep(0.8)  # o 'app reaberto' (hostname) sai sozinho; libera o handle
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
