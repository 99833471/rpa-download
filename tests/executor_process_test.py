"""Testa o subprocesso executor de ponta a ponta (headless, sem login):
manifesto -> execução -> arquivo baixado + log + evento 'done' no stdout + exit 0.

Uso:  python tests/executor_process_test.py
"""

from __future__ import annotations

import json
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
        manifest_path = os.path.join(d, "robot.json")
        manifest.save(manifest_path)
        download_dir = os.path.join(d, "robot")
        os.makedirs(download_dir, exist_ok=True)
        log_path = os.path.join(download_dir, "run.log")

        proc = subprocess.run(
            [sys.executable, "-m", "app.executor.executor_process",
             "--manifest", manifest_path, "--download-dir", download_dir, "--log", log_path],
            cwd=_ROOT, capture_output=True, text=True, timeout=120,
        )

        print("== Subprocesso executor ==")
        check("saiu com código 0", proc.returncode == 0)
        # Ignora os logs (run.log/run.csv) — conta só o arquivo baixado.
        files = [f for f in os.listdir(download_dir) if not f.startswith("run.")]
        check("um arquivo baixado", len(files) == 1)
        check("log .csv detalhado gerado", os.path.isfile(os.path.join(download_dir, "run.csv")))
        if files:
            check("arquivo com timestamp", files[0].endswith(" - relatorio.csv"))
            check("arquivo não vazio", os.path.getsize(os.path.join(download_dir, files[0])) > 0)
        check("log de execução criado", os.path.isfile(log_path) and os.path.getsize(log_path) > 0)

        done_events = [json.loads(l) for l in proc.stdout.splitlines()
                       if l.strip().startswith("{") and '"done"' in l]
        check("emitiu evento done ok", bool(done_events) and done_events[-1].get("ok") is True)

    print()
    if _failures:
        print(f"RESULTADO: {len(_failures)} falha(s): {_failures}")
        return 1
    print("RESULTADO: subprocesso executor - OK")
    return 0


if __name__ == "__main__":
    sys.exit(main())
