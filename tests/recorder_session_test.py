"""Testa o núcleo da gravação (RecordingSession) e o subprocesso recorder_process.

- Núcleo: dirige eventos headless e confere montagem de passos (goto/fill/click/
  download) + storage_state.
- Subprocesso: roda recorder_process headless com auto-finish e confere que grava
  os passos e a sessão criptografada, saindo com código 0.

Uso:  python tests/recorder_session_test.py
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile

_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, _ROOT)

from playwright.sync_api import sync_playwright  # noqa: E402

from app.recorder.recorder_core import RecordingSession  # noqa: E402
from app.services import crypto  # noqa: E402

_failures = []

_HTML = """<!doctype html><html><head><meta charset="utf-8"></head><body>
<input id="campo-data" name="data" placeholder="Data">
<a id="dl" href="data:text/csv,col1,col2%0A1,2" download="relatorio.csv">Baixar</a>
</body></html>
"""


def check(label, cond):
    print(f"  [{'OK ' if cond else 'FALHOU'}] {label}")
    if not cond:
        _failures.append(label)


def _write_html(d):
    p = os.path.join(d, "page.html")
    with open(p, "w", encoding="utf-8") as f:
        f.write(_HTML)
    return "file:///" + p.replace("\\", "/")


def test_core():
    print("== Núcleo da gravação (RecordingSession) ==")
    with tempfile.TemporaryDirectory() as d:
        url = _write_html(d)
        with sync_playwright() as pw:
            browser = pw.chromium.launch(headless=True)
            context = browser.new_context(accept_downloads=True)
            page = context.new_page()
            session = RecordingSession(start_url=url)
            session.attach(context, page)

            page.goto(url)
            page.wait_for_timeout(200)
            page.fill("#campo-data", "01/06/2026")
            page.locator("#campo-data").blur()
            page.wait_for_timeout(150)
            page.click("#dl")
            page.wait_for_timeout(500)

            session._on_control(None, "finish")
            summary, state = session.build_result()
            browser.close()

    actions = [s["action"] for s in summary["steps"]]
    check("primeiro passo é goto", actions and actions[0] == "goto")
    check("gravou um fill", "fill" in actions)
    fills = [s for s in summary["steps"] if s["action"] == "fill"]
    check("valor do fill correto", fills and fills[0]["value"] == "01/06/2026")
    check("gravou o clique no link", "click" in actions)
    check("gravou o marcador de download", "download" in actions)
    check("storage_state retornado é dict", isinstance(state, dict))


def test_subprocess():
    print("== Subprocesso recorder_process (headless + auto-finish) ==")
    with tempfile.TemporaryDirectory() as d:
        url = _write_html(d)
        steps_out = os.path.join(d, "steps.json")
        session_out = os.path.join(d, "session.bin")
        proc = subprocess.run(
            [sys.executable, "-m", "app.recorder.recorder_process",
             "--headless", "--auto-finish-ms", "1200",
             "--start-url", url, "--steps-out", steps_out, "--session-out", session_out],
            cwd=_ROOT, capture_output=True, text=True, timeout=90,
        )
        check("subprocesso saiu com código 0", proc.returncode == 0)
        check("arquivo de passos foi criado", os.path.isfile(steps_out))
        check("arquivo de sessão foi criado", os.path.isfile(session_out))
        if os.path.isfile(steps_out):
            with open(steps_out, encoding="utf-8") as f:
                summary = json.load(f)
            check("passos contém start_url", summary.get("start_url") == url)
            check("passos é uma lista", isinstance(summary.get("steps"), list))
        if os.path.isfile(session_out):
            state = json.loads(crypto.load_text_encrypted(session_out))
            check("sessão descriptografa para dict", isinstance(state, dict))


def main():
    test_core()
    test_subprocess()
    print()
    if _failures:
        print(f"RESULTADO: {len(_failures)} falha(s): {_failures}")
        return 1
    print("RESULTADO: gravador (núcleo + subprocesso) - OK")
    return 0


if __name__ == "__main__":
    sys.exit(main())
