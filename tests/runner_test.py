"""Testa o runner standalone (não-congelado): executa um robô a partir de uma
pasta com robot.json e salva o download na pasta de saída.

Uso:  python tests/runner_test.py
"""

from __future__ import annotations

import os
import subprocess
import sys
import tempfile

_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, _ROOT)

from app.robot_manifest import FieldConfig, RobotManifest, Selector, Step  # noqa: E402

_failures = []


def check(label, cond):
    print(f"  [{'OK ' if cond else 'FALHOU'}] {label}")
    if not cond:
        _failures.append(label)


def main():
    with tempfile.TemporaryDirectory() as d:
        html = ('<input id="data" name="data">'
                '<a id="dl" href="data:text/csv,a,b%0A1,2" download="relatorio.csv">Baixar</a>')
        page = os.path.join(d, "page.html")
        with open(page, "w", encoding="utf-8") as f:
            f.write(html)
        url = "file:///" + page.replace("\\", "/")

        robot_dir = os.path.join(d, "robot")
        os.makedirs(robot_dir, exist_ok=True)
        RobotManifest(
            name="Robô Teste", start_url=url,
            steps=[
                Step(action="goto", url=url),
                Step(action="fill", selectors=[Selector("id", "#data")],
                     field=FieldConfig(type="fixed", value="01/06/2026")),
                Step(action="click", selectors=[Selector("id", "#dl")]),
                Step(action="download"),
            ],
        ).save(os.path.join(robot_dir, "robot.json"))

        out_dir = os.path.join(d, "saida")
        proc = subprocess.run(
            [sys.executable, "-m", "app.exporter.robot_runner",
             "--robot-dir", robot_dir, "--out-dir", out_dir],
            cwd=_ROOT, capture_output=True, text=True, timeout=120,
        )

        print("== Runner standalone ==")
        check("saiu com código 0", proc.returncode == 0)
        dldir = os.path.join(out_dir, "downloads")
        files = os.listdir(dldir) if os.path.isdir(dldir) else []
        check("baixou um arquivo", len(files) == 1)
        if files:
            check("arquivo com timestamp", files[0].endswith(" - relatorio.csv"))
        check("gerou run.log", os.path.isfile(os.path.join(out_dir, "run.log")))

    print()
    if _failures:
        print(f"RESULTADO: {len(_failures)} falha(s): {_failures}")
        return 1
    print("RESULTADO: runner standalone - OK")
    return 0


if __name__ == "__main__":
    sys.exit(main())
