"""Testa o planner puro de particionamento e a integração com o executor usando
um site fake que só libera o download quando o intervalo é pequeno.

Uso:  python tests/partition_test.py
"""

from __future__ import annotations

import os
import sys
import tempfile
from datetime import date, timedelta

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from playwright.sync_api import sync_playwright  # noqa: E402

from app.executor.executor_core import ExecutionEngine  # noqa: E402
from app.executor.partition import partition_plan  # noqa: E402
from app.robot_manifest import FieldConfig, RobotManifest, Selector, SiteLimit, Step  # noqa: E402

_failures = []


def check(label, cond):
    print(f"  [{'OK ' if cond else 'FALHOU'}] {label}")
    if not cond:
        _failures.append(label)


def test_planner():
    print("== Planner puro ==")
    start, end = date(2026, 6, 1), date(2026, 6, 8)  # 8 dias
    # Libera se o intervalo tem no máximo 3 dias.
    ok, fail = partition_plan(start, end, lambda a, b: (b - a).days + 1 <= 3)
    check("nenhuma faixa falhou", fail == [])
    check("todas as faixas têm <= 3 dias", all((b - a).days + 1 <= 3 for a, b in ok))
    # Cobertura contígua e sem sobreposição.
    contiguous = ok[0][0] == start and ok[-1][1] == end
    for (a1, b1), (a2, b2) in zip(ok, ok[1:]):
        if a2 != b1 + timedelta(days=1):
            contiguous = False
    check("cobre o intervalo sem lacunas/sobreposição", contiguous)

    # Caso em que um dia isolado nunca libera.
    ok2, fail2 = partition_plan(start, end, lambda a, b: False)
    check("dias isolados caem em 'falhos'", len(fail2) == 8 and ok2 == [])


def test_integration(pw, d):
    print("== Particionamento no executor (site fake) ==")
    html = """<!doctype html><meta charset="utf-8">
    <input id="ini"><input id="fim">
    <button id="baixar">Baixar</button><div id="erro"></div>
    <script>
      function parse(s){const p=s.split('/').map(Number);return new Date(p[2],p[1]-1,p[0]);}
      document.getElementById('baixar').addEventListener('click',function(){
        var a=parse(document.getElementById('ini').value);
        var b=parse(document.getElementById('fim').value);
        var days=Math.round((b-a)/86400000)+1;
        if(days<=3){var x=document.createElement('a');
          x.href='data:text/csv,'+encodeURIComponent('ok');x.download='dados.csv';
          document.body.appendChild(x);x.click();x.remove();}
        else{document.getElementById('erro').textContent='LIMITE EXCEDIDO';}
      });
    </script>"""
    p = os.path.join(d, "limit.html")
    with open(p, "w", encoding="utf-8") as f:
        f.write(html)
    url = "file:///" + p.replace("\\", "/")

    manifest = RobotManifest(
        name="t", start_url=url,
        site_limit=SiteLimit(enabled=True, max_rows=3, strategy="date_partition",
                             start_date_step=1, end_date_step=2),
        steps=[
            Step(action="goto", url=url),
            Step(action="fill", selectors=[Selector("id", "#ini")],
                 field=FieldConfig(type="fixed", value="01/06/2026", fmt="dd/mm/yyyy")),
            Step(action="fill", selectors=[Selector("id", "#fim")],
                 field=FieldConfig(type="fixed", value="08/06/2026", fmt="dd/mm/yyyy")),
            Step(action="click", selectors=[Selector("id", "#baixar")]),
            Step(action="download"),
        ],
    )
    dldir = os.path.join(d, "out")
    browser = pw.chromium.launch(headless=True)
    page = browser.new_context(accept_downloads=True).new_page()
    engine = ExecutionEngine(page, manifest, dldir, action_timeout=3000,
                             partition_download_timeout=2500)
    res = engine.execute()
    browser.close()

    files = os.listdir(dldir) if os.path.isdir(dldir) else []
    check("execução particionada OK", res.ok)
    check("baixou múltiplos arquivos (1 por período)", len(files) >= 3)
    check("todos os arquivos não vazios",
          all(os.path.getsize(os.path.join(dldir, f)) > 0 for f in files))


def main():
    test_planner()
    with tempfile.TemporaryDirectory() as d, sync_playwright() as pw:
        test_integration(pw, d)
    print()
    if _failures:
        print(f"RESULTADO: {len(_failures)} falha(s): {_failures}")
        return 1
    print("RESULTADO: particionamento adaptativo - OK")
    return 0


if __name__ == "__main__":
    sys.exit(main())
