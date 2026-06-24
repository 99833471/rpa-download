"""Construção do executável (.exe) de um robô via PyInstaller (runner leve).

O .exe embute o robot.json e a sessão, mas NÃO o navegador — o Chromium é baixado
na primeira execução (mantém o arquivo pequeno e compartilhável).
"""

from __future__ import annotations

import os

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
RUNNER = os.path.join(PROJECT_ROOT, "app", "exporter", "robot_runner.py")


def build_args(python_exe: str, robot_dir: str, output_name: str,
               dest_dir: str, work_dir: str) -> list[str]:
    """Monta a linha de comando do PyInstaller para empacotar um robô."""
    robot_json = os.path.join(robot_dir, "robot.json")
    session = os.path.join(robot_dir, "session.bin")

    args = [
        python_exe, "-m", "PyInstaller",
        "--noconfirm", "--onefile", "--console",
        "--name", output_name,
        "--paths", PROJECT_ROOT,
        "--collect-all", "playwright",
        "--distpath", dest_dir,
        "--workpath", os.path.join(work_dir, "build"),
        "--specpath", work_dir,
        "--add-data", f"{robot_json}{os.pathsep}.",
    ]
    if os.path.isfile(session):
        args += ["--add-data", f"{session}{os.pathsep}."]
    args.append(RUNNER)
    return args


def exe_path(dest_dir: str, output_name: str) -> str:
    suffix = ".exe" if os.name == "nt" else ""
    return os.path.join(dest_dir, output_name + suffix)
