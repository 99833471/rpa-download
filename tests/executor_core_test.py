"""Testa o núcleo do executor headless: naming/integridade de download, evasão de
pop-up (clique interceptado), fallback de seletor e detecção de login.

Uso:  python tests/executor_core_test.py
"""

from __future__ import annotations

import os
import sys
import tempfile

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from playwright.sync_api import sync_playwright  # noqa: E402

from app.executor.executor_core import (  # noqa: E402
    ExecutionEngine, has_timestamp, has_visible_password, timestamp_filename,
)
from app.robot_manifest import FieldConfig, RobotManifest, Selector, Step  # noqa: E402

_failures = []


def check(label, cond):
    print(f"  [{'OK ' if cond else 'FALHOU'}] {label}")
    if not cond:
        _failures.append(label)


def _url(d, name, html):
    p = os.path.join(d, name)
    with open(p, "w", encoding="utf-8") as f:
        f.write(html)
    return "file:///" + p.replace("\\", "/")


def test_naming():
    print("== Naming / integridade ==")
    check("nome sem timestamp ganha prefixo",
          timestamp_filename("relatorio.csv").endswith(" - relatorio.csv")
          and timestamp_filename("relatorio.csv")[:4].isdigit())
    check("nome com data mantém original (yyyymmdd)",
          timestamp_filename("Custos_20260624.xlsx") == "Custos_20260624.xlsx")
    check("nome com data ISO mantém original",
          timestamp_filename("dados 2026-06-24.csv") == "dados 2026-06-24.csv")
    check("has_timestamp detecta", has_timestamp("x_20260101.csv") and not has_timestamp("abc.csv"))


def test_download(pw, d):
    print("== Download (captura + naming) ==")
    html = (
        '<input id="data" name="data">'
        '<a id="dl" href="data:text/csv,a,b%0A1,2" download="relatorio.csv">Baixar</a>'
    )
    url = _url(d, "dl.html", html)
    manifest = RobotManifest(
        name="t", start_url=url,
        steps=[
            Step(action="goto", url=url),
            Step(action="fill", selectors=[Selector("id", "#data")],
                 field=FieldConfig(type="fixed", value="01/06/2026")),
            Step(action="click", selectors=[Selector("id", "#dl")]),
            Step(action="download"),
        ],
    )
    dldir = os.path.join(d, "out")
    browser = pw.chromium.launch(headless=True)
    page = browser.new_context(accept_downloads=True).new_page()
    res = ExecutionEngine(page, manifest, dldir, action_timeout=4000).run()
    browser.close()

    check("execução OK", res.ok)
    files = os.listdir(dldir) if os.path.isdir(dldir) else []
    check("um arquivo baixado", len(files) == 1)
    if files:
        check("arquivo nomeado com timestamp", files[0].endswith(" - relatorio.csv"))
        check("arquivo não está vazio", os.path.getsize(os.path.join(dldir, files[0])) > 0)


def test_download_no_marker(pw, d):
    print("== Download SEM marcador (capturado globalmente) ==")
    html = '<a id="dl" href="data:text/csv,a,b%0A1,2" download="rel.csv">Baixar</a>'
    url = _url(d, "dlnm.html", html)
    # Manifesto termina no clique, SEM passo 'download' (caso do robô do usuário).
    manifest = RobotManifest(name="t", start_url=url, steps=[
        Step(action="goto", url=url),
        Step(action="click", selectors=[Selector("id", "#dl")]),
    ])
    dldir = os.path.join(d, "outnm")
    browser = pw.chromium.launch(headless=True)
    page = browser.new_context(accept_downloads=True).new_page()
    res = ExecutionEngine(page, manifest, dldir, action_timeout=4000).run()
    browser.close()
    files = os.listdir(dldir) if os.path.isdir(dldir) else []
    check("execução OK", res.ok)
    check("baixou mesmo sem marcador de download", len(files) == 1)
    if files:
        check("arquivo com timestamp", files[0].endswith(" - rel.csv"))


def test_optional_step(pw, d):
    print("== Passo opcional (pop-up que não apareceu) ==")
    html = ('<input id="data" name="data">'
            '<a id="dl" href="data:text/csv,a%0A1" download="rel.csv">Baixar</a>')
    url = _url(d, "opt.html", html)
    manifest = RobotManifest(name="t", start_url=url, steps=[
        Step(action="goto", url=url),
        # pop-up que NÃO existe nesta execução -> deve ser pulado sem erro
        Step(action="click", name="Fechar avaliação", optional=True,
             selectors=[Selector("id", "#popup-inexistente")]),
        Step(action="click", selectors=[Selector("id", "#dl")]),
    ])
    dldir = os.path.join(d, "opt_out")
    browser = pw.chromium.launch(headless=True)
    page = browser.new_context(accept_downloads=True).new_page()
    res = ExecutionEngine(page, manifest, dldir, action_timeout=2000).run()
    browser.close()
    files = os.listdir(dldir) if os.path.isdir(dldir) else []
    check("execução OK mesmo sem o pop-up", res.ok)
    check("baixou o arquivo após pular o opcional", len(files) == 1)


def test_popup_evasion(pw, d):
    print("== Evasão de pop-up (clique interceptado) ==")
    html = (
        '<button id="target" onclick="window.__clicked=true">Alvo</button>'
        '<div id="ov" style="position:fixed;inset:0;background:rgba(0,0,0,.6);z-index:9999;'
        'display:flex;align-items:center;justify-content:center">'
        '<button onclick="document.getElementById(\'ov\').remove()">Aceitar</button></div>'
    )
    url = _url(d, "popup.html", html)
    manifest = RobotManifest(name="t", start_url=url, steps=[
        Step(action="goto", url=url),
        Step(action="click", selectors=[Selector("id", "#target")]),
    ])
    browser = pw.chromium.launch(headless=True)
    page = browser.new_context().new_page()
    res = ExecutionEngine(page, manifest, os.path.join(d, "o2"),
                          action_timeout=2500, max_attempts=3, backoff_base=0.1).run()
    clicked = bool(page.evaluate("window.__clicked === true"))
    browser.close()
    check("execução OK após fechar pop-up", res.ok)
    check("alvo realmente clicado", clicked)


def test_selector_fallback(pw, d):
    print("== Fallback de seletor ==")
    html = '<button id="alvo2" onclick="window.__c2=true">T2</button>'
    url = _url(d, "fb.html", html)
    manifest = RobotManifest(name="t", start_url=url, steps=[
        Step(action="goto", url=url),
        Step(action="click", selectors=[Selector("css", "#naoexiste"), Selector("id", "#alvo2")]),
    ])
    browser = pw.chromium.launch(headless=True)
    page = browser.new_context().new_page()
    res = ExecutionEngine(page, manifest, os.path.join(d, "o3"),
                          action_timeout=800, max_attempts=2, backoff_base=0.05).run()
    clicked = bool(page.evaluate("window.__c2 === true"))
    browser.close()
    check("execução OK usando 2º seletor", res.ok)
    check("clique caiu no seletor de fallback", clicked)


def test_login_detection(pw, d):
    print("== Detecção de sessão expirada ==")
    url_login = _url(d, "login.html", '<input type="password" id="p">')
    url_ok = _url(d, "ok.html", '<div>logado</div>')
    browser = pw.chromium.launch(headless=True)
    page = browser.new_context().new_page()
    page.goto(url_login)
    has_pwd = has_visible_password(page)
    page.goto(url_ok)
    no_pwd = has_visible_password(page)
    browser.close()
    check("detecta campo de senha visível", has_pwd is True)
    check("não detecta quando não há senha", no_pwd is False)


def main():
    test_naming()
    with tempfile.TemporaryDirectory() as d, sync_playwright() as pw:
        test_download(pw, d)
        test_download_no_marker(pw, d)
        test_optional_step(pw, d)
        test_popup_evasion(pw, d)
        test_selector_fallback(pw, d)
        test_login_detection(pw, d)
    print()
    if _failures:
        print(f"RESULTADO: {len(_failures)} falha(s): {_failures}")
        return 1
    print("RESULTADO: núcleo do executor - OK")
    return 0


if __name__ == "__main__":
    sys.exit(main())
