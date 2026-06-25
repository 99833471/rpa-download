"""Orquestra a geração do .exe de um robô (PyInstaller) em background (QProcess)."""

from __future__ import annotations

import os
import shutil
import sys
import tempfile

from PySide6.QtCore import QObject, QProcess, Signal
from PySide6.QtWidgets import QFileDialog, QMessageBox

from ..exporter.build_exe import build_args, exe_path
from ..sanitize import sanitize_name
from . import dialogs


class ExportController(QObject):
    statusMessage = Signal(str)

    def __init__(self, db, mirror, parent_widget):
        super().__init__(parent_widget)
        self.db = db
        self.mirror = mirror
        self.parent = parent_widget
        self.proc: QProcess | None = None
        self._ctx: dict | None = None
        self._buf = ""

    def is_running(self) -> bool:
        return self.proc is not None

    def export(self, robot_id: int) -> None:
        if getattr(sys, "frozen", False):
            dialogs.info(
                self.parent, "Indisponível no executável",
                "A geração de .exe por robô requer a versão instalada via código\n"
                "(Python + PyInstaller). Rode o programa a partir do código-fonte\n"
                "para exportar robôs individualmente.",
            )
            return
        if self.is_running():
            dialogs.info(self.parent, "Exportação em andamento",
                         "Aguarde a geração atual terminar.")
            return
        robot = self.db.get_robot(robot_id)
        if robot is None:
            return
        robot_dir = self.mirror.robot_dir(robot_id)
        if not os.path.isfile(os.path.join(robot_dir, "robot.json")):
            dialogs.info(self.parent, "Robô sem caminho",
                         "Grave o robô (Refazer caminho) antes de gerar o executável.")
            return

        name = dialogs.ask_text(self.parent, "Gerar executável",
                                "Nome do executável:", sanitize_name(robot.name))
        if not name:
            return
        name = sanitize_name(name)
        if name.lower().endswith(".exe"):
            name = name[:-4]

        dest = QFileDialog.getExistingDirectory(self.parent, "Onde salvar o .exe", robot_dir)
        if not dest:
            return

        work = tempfile.mkdtemp(prefix="rpa_build_")
        args = build_args(sys.executable, robot_dir, name, dest, work)

        proc = QProcess(self)
        proc.setProgram(args[0])
        proc.setArguments(args[1:])
        proc.setProcessChannelMode(QProcess.MergedChannels)
        proc.readyReadStandardOutput.connect(self._on_output)
        proc.finished.connect(self._on_finished)
        proc.errorOccurred.connect(self._on_error)

        self._ctx = {"name": name, "dest": dest, "work": work, "robot_id": robot_id}
        self._buf = ""
        self.proc = proc
        self.statusMessage.emit(f"Gerando executável “{name}.exe”… (pode levar alguns minutos)")
        proc.start()

    # ------------------------------------------------------------- eventos
    def _on_output(self):
        if self.proc is None:
            return
        self._buf += bytes(self.proc.readAllStandardOutput()).decode("utf-8", errors="replace")
        self._buf = self._buf[-8000:]  # mantém só a cauda

    def _on_error(self, error):
        if self.proc is None:
            return
        if error == QProcess.FailedToStart:
            ctx = self._ctx
            self._reset()
            self.statusMessage.emit("Falha ao iniciar o PyInstaller.")
            QMessageBox.warning(
                self.parent, "Exportação",
                "Não foi possível iniciar o PyInstaller.\n"
                "Instale com:  pip install pyinstaller",
            )
            if ctx:
                self._cleanup(ctx)

    def _on_finished(self, code, _status):
        ctx = self._ctx
        self._reset()
        if ctx is None:
            return
        target = exe_path(ctx["dest"], ctx["name"])
        if code == 0 and os.path.isfile(target):
            self.statusMessage.emit(f"Executável gerado: {target}")
            QMessageBox.information(
                self.parent, "Executável gerado",
                f"Robô exportado com sucesso:\n{target}\n\n"
                "Na primeira execução em outra máquina, o navegador é baixado "
                "automaticamente e o login (se houver) será solicitado.",
            )
        else:
            self.statusMessage.emit("Falha ao gerar o executável.")
            tail = self._buf[-1500:] if self._buf else "(sem saída)"
            QMessageBox.warning(self.parent, "Falha na exportação",
                                f"Não foi possível gerar o .exe.\n\nÚltimas mensagens:\n{tail}")
        self._cleanup(ctx)

    # ------------------------------------------------------------- helpers
    def _reset(self):
        if self.proc is not None:
            self.proc.deleteLater()
        self.proc = None

    def _cleanup(self, ctx):
        try:
            shutil.rmtree(ctx["work"], ignore_errors=True)
        except OSError:
            pass
