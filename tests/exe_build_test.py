"""Validação end-to-end da exportação .exe (LENTO — build com PyInstaller).

Constrói o .exe de um robô de teste e o executa, conferindo que ele baixa o
arquivo. NÃO faz parte da suíte rápida (leva alguns minutos).

Uso:  python tests/exe_build_test.py
"""

from __future__ import annotations

import os
import subprocess
import sys
import tempfile

_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, _ROOT)

from app.exporter.build_exe import build_args, exe_path  # noqa: E402
from app.robot_manifest import FieldConfig, RobotManifest, Selector, Step  # noqa: E402

_failures = []


def check(label, cond):
    print(f"  [{'OK ' if cond else 'FALHOU'}] {label}", flush=True)
    if not cond:
        _failures.append(label)


def main():
    work = tempfile.mkdtemp(prefix="rpa_exe_test_")
    page = os.path.join(work, "page.html")
    with open(page, "w", encoding="utf-8") as f:
        f.write('<input id="data" name="data">'
                '<a id="dl" href="data:text/csv,a,b%0A1,2" download="relatorio.csv">Baixar</a>')
    url = "file:///" + page.replace("\\", "/")

    robot_dir = os.path.join(work, "robot")
    os.makedirs(robot_dir, exist_ok=True)
    RobotManifest(
        name="RoboExe", start_url=url,
        steps=[
            Step(action="goto", url=url),
            Step(action="fill", selectors=[Selector("id", "#data")],
                 field=FieldConfig(type="fixed", value="01/06/2026")),
            Step(action="click", selectors=[Selector("id", "#dl")]),
            Step(action="download"),
        ],
    ).save(os.path.join(robot_dir, "robot.json"))

    dest = os.path.join(work, "dist")
    build_work = os.path.join(work, "buildwork")
    os.makedirs(dest, exist_ok=True)

    print("== Build do .exe (pode levar alguns minutos) ==", flush=True)
    args = build_args(sys.executable, robot_dir, "RoboExe", dest, build_work)
    bp = subprocess.run(args, cwd=_ROOT, capture_output=True, text=True,
                        encoding="utf-8", errors="replace", timeout=900)
    target = exe_path(dest, "RoboExe")
    check("PyInstaller saiu com código 0", bp.returncode == 0)
    check("arquivo .exe foi gerado", os.path.isfile(target))
    if not os.path.isfile(target):
        print(bp.stdout[-2000:])
        print(bp.stderr[-2000:])
        return 1

    size_mb = os.path.getsize(target) / (1024 * 1024)
    print(f"  .exe gerado: {target} ({size_mb:.1f} MB)", flush=True)

    print("== Executando o .exe ==", flush=True)
    out_dir = os.path.join(work, "saida")
    rp = subprocess.run([target, "--out-dir", out_dir],
                        stdin=subprocess.DEVNULL, capture_output=True, text=True,
                        encoding="utf-8", errors="replace", timeout=300)
    check(".exe executou com código 0", rp.returncode == 0)
    dldir = os.path.join(out_dir, "downloads")
    files = os.listdir(dldir) if os.path.isdir(dldir) else []
    check(".exe baixou um arquivo", len(files) == 1)
    if rp.returncode != 0:
        print(rp.stdout[-1500:])

    print()
    if _failures:
        print(f"RESULTADO: {len(_failures)} falha(s): {_failures}")
        return 1
    print("RESULTADO: exportação .exe - OK")
    print(f"(artefatos em {work} — pode apagar)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
