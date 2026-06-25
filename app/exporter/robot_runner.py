"""Runner standalone de um robô — entrada do executável (.exe) compartilhável.

Funciona congelado (PyInstaller) e não-congelado (para testes):
- Congelado: lê o robot.json/session.bin embutidos (sys._MEIPASS) e grava os
  downloads e a sessão de trabalho ao lado do .exe.
- Não-congelado: receba --robot-dir e --out-dir.

Estratégia "runner leve": o navegador NÃO é embutido; na primeira execução, se o
Chromium não estiver disponível, ele é baixado automaticamente.
"""

from __future__ import annotations

import argparse
import os
import shutil
import sys

_FROZEN = getattr(sys, "frozen", False)

# IMPORTANTE: fixar um local de navegadores ESTÁVEL (fora do bundle) antes de
# importar o Playwright. Sem isto, o exe congelado procura o Chromium dentro do
# pacote temporário (_MEIxxxx/.local-browsers) e não o encontra. Apontando para o
# diretório padrão do usuário, a máquina que já tem o navegador o reaproveita e a
# máquina nova baixa para o lugar certo (runner leve).
if not os.environ.get("PLAYWRIGHT_BROWSERS_PATH"):
    _base = os.environ.get("LOCALAPPDATA") or os.path.expanduser("~")
    os.environ["PLAYWRIGHT_BROWSERS_PATH"] = os.path.join(_base, "ms-playwright")

if not _FROZEN:
    # Permite importar o pacote "app" ao rodar como script.
    sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from app.executor.browser import ensure_chromium  # noqa: E402
from app.robot_manifest import FIELD_FIXED, FIELD_FORMULA, FIELD_MANUAL, RobotManifest  # noqa: E402
from app import formula  # noqa: E402
from app.executor import executor_process  # noqa: E402


def resolve_fields(manifest: RobotManifest):
    try:
        import holidays
        br = holidays.Brazil()
    except Exception:
        br = None
    for step in manifest.steps:
        if step.field is None:
            continue
        kind = step.field.type
        if kind == FIELD_FORMULA:
            try:
                value = formula.evaluate(step.field.formula,
                                         fmt=step.field.fmt or "dd/mm/yyyy",
                                         holiday_calendar=br)
            except formula.FormulaError as e:
                print(f"Fórmula inválida em '{step.label}': {e}")
                sys.exit(3)
        elif kind == FIELD_MANUAL:
            value = input(f"{step.field.prompt or step.label or 'Informe o valor'}: ").strip()
        else:
            value = step.field.value
        step.field.value = value
        step.field.type = FIELD_FIXED
    return manifest


def _paths(argv):
    p = argparse.ArgumentParser(description="Executa um robô exportado.")
    p.add_argument("--robot-dir", default="")
    p.add_argument("--out-dir", default="")
    args = p.parse_args(argv)

    if _FROZEN:
        robot_dir = getattr(sys, "_MEIPASS", os.path.dirname(sys.executable))
        out_dir = args.out_dir or os.path.dirname(sys.executable)
    else:
        if not args.robot_dir:
            p.error("--robot-dir é obrigatório fora do executável.")
        robot_dir = args.robot_dir
        out_dir = args.out_dir or os.path.join(os.getcwd(), "saida_robo")
    return robot_dir, out_dir


def main(argv=None) -> int:
    robot_dir, out_dir = _paths(argv if argv is not None else sys.argv[1:])
    manifest_path = os.path.join(robot_dir, "robot.json")
    if not os.path.isfile(manifest_path):
        print("robot.json não encontrado no pacote.")
        return 3

    manifest = RobotManifest.load(manifest_path)
    print(f"== Robô: {manifest.name} ==")

    os.makedirs(out_dir, exist_ok=True)
    downloads_dir = os.path.join(out_dir, "downloads")
    working_session = os.path.join(out_dir, "session.bin")
    bundled_session = os.path.join(robot_dir, "session.bin")
    if not os.path.isfile(working_session) and os.path.isfile(bundled_session):
        try:
            shutil.copyfile(bundled_session, working_session)
        except OSError:
            pass

    resolve_fields(manifest)
    resolved_path = os.path.join(out_dir, "_resolved_robot.json")
    manifest.save(resolved_path)

    ensure_chromium(print)

    rc = executor_process.main([
        "--manifest", resolved_path,
        "--download-dir", downloads_dir,
        "--session-in", working_session,
        "--log", os.path.join(out_dir, "run.log"),
    ])

    try:
        os.remove(resolved_path)
    except OSError:
        pass

    if rc == 0:
        print(f"\nConcluído. Arquivos salvos em: {downloads_dir}")
    elif rc == 2:
        print("\nExecução cancelada.")
    else:
        print("\nFinalizado com erro (ver run.log).")

    # Pausa só quando há console interativo (evita travar em execução automatizada).
    if _FROZEN and sys.stdin is not None and sys.stdin.isatty():
        try:
            input("\nPressione Enter para sair…")
        except EOFError:
            pass
    return rc


if __name__ == "__main__":
    sys.exit(main())
