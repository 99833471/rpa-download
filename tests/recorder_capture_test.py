"""Valida a captura de seletores do recorder.js dirigindo eventos por código
(Playwright headless) — sem interação manual.

Uso:  python tests/recorder_capture_test.py
"""

from __future__ import annotations

import json
import os
import sys
import tempfile

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from playwright.sync_api import sync_playwright  # noqa: E402

_failures = []
_RECORDER_JS = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    "app", "recorder", "recorder.js",
)

_HTML = """<!doctype html><html><head><meta charset="utf-8"><title>Teste</title></head>
<body>
  <h1>Relatório</h1>
  <label for="campo-data">Data inicial</label>
  <input id="campo-data" name="data" placeholder="Data inicial">
  <select id="sel-tipo" name="tipo">
    <option value="a">Opção A</option>
    <option value="b">Opção B</option>
  </select>
  <input id="senha" name="pwd" type="password">
  <button id="btn-baixar" data-testid="download-btn">Baixar relatório</button>
  <div id="auto-12345678">ruído</div>
</body></html>
"""


def check(label, cond):
    print(f"  [{'OK ' if cond else 'FALHOU'}] {label}")
    if not cond:
        _failures.append(label)


def types(ev):
    return [s["type"] for s in ev["selectors"]]


def values(ev):
    return [s["value"] for s in ev["selectors"]]


def main():
    events = []

    with tempfile.TemporaryDirectory() as d:
        html_path = os.path.join(d, "page.html")
        with open(html_path, "w", encoding="utf-8") as f:
            f.write(_HTML)

        with sync_playwright() as pw:
            browser = pw.chromium.launch(headless=True)
            context = browser.new_context()
            context.expose_binding("__rpa_record",
                                   lambda source, arg: events.append(json.loads(arg)))
            context.expose_binding("__rpa_control", lambda source, action: None)
            with open(_RECORDER_JS, "r", encoding="utf-8") as f:
                context.add_init_script(f.read())

            page = context.new_page()
            page.goto("file:///" + html_path.replace("\\", "/"))
            page.wait_for_timeout(200)

            # Preenche o campo de data e dispara 'change' via blur.
            page.fill("#campo-data", "01/06/2026")
            page.locator("#campo-data").blur()
            page.wait_for_timeout(100)

            # Seleciona opção.
            page.select_option("#sel-tipo", "b")
            page.wait_for_timeout(100)

            # Digita senha (NÃO deve ser gravada).
            page.fill("#senha", "segredo123")
            page.locator("#senha").blur()
            page.wait_for_timeout(100)

            # Clica no botão de download.
            page.click("#btn-baixar")
            page.wait_for_timeout(150)

            browser.close()

    print("== Captura de eventos ==")
    fills = [e for e in events if e["action"] == "fill"]
    selects = [e for e in events if e["action"] == "select"]
    clicks = [e for e in events if e["action"] == "click"]

    check("capturou 1 preenchimento (sem a senha)", len(fills) == 1)
    check("valor do preenchimento correto", fills and fills[0]["value"] == "01/06/2026")
    check("nenhuma senha vazou nos eventos",
          all("segredo123" not in (e.get("value") or "") for e in events))

    if fills:
        check("data: id é o 1º candidato", types(fills[0])[0] == "id"
              and values(fills[0])[0] == "#campo-data")
        check("data: inclui seletor por name", '[name="data"]' in " ".join(values(fills[0])))
        check("data: xpath é o último candidato", types(fills[0])[-1] == "xpath")

    check("capturou o select", len(selects) == 1 and selects[0]["value"] == "b")

    check("capturou o clique no botão", len(clicks) == 1)
    if clicks:
        ct = types(clicks[0])
        cv = values(clicks[0])
        check("botão: id é o 1º candidato", ct[0] == "id" and cv[0] == "#btn-baixar")
        check("botão: inclui data-testid", any('data-testid="download-btn"' in v for v in cv))
        check("botão: inclui candidato por texto", "text" in ct)

    print()
    if _failures:
        print(f"RESULTADO: {len(_failures)} falha(s): {_failures}")
        return 1
    print("RESULTADO: captura de seletores - OK")
    return 0


if __name__ == "__main__":
    sys.exit(main())
