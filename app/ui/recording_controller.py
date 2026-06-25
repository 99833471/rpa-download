"""Orquestra a gravação de um robô: lança o subprocesso (QProcess), abre a revisão
e grava o robot.json — com fail-safe.

Fail-safe (requisito): se a gravação/refação for abandonada (cancelar no
navegador, descartar na revisão ou erro), o robô anterior é restaurado por
completo (robot.json + sessão), sem aplicar alterações.
"""

from __future__ import annotations

import json
import os
import sys
import tempfile

from PySide6.QtCore import QObject, QProcess, Signal
from PySide6.QtWidgets import QDialog, QMessageBox

from ..subproc import child_command
from . import dialogs
from .recording_review import RecordingReviewDialog

# .../app/ui/recording_controller.py -> raiz do projeto
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def _read_bytes(path):
    return open(path, "rb").read() if os.path.isfile(path) else None


def _write_or_remove(path, data):
    if data is None:
        if os.path.isfile(path):
            try:
                os.remove(path)
            except OSError:
                pass
    else:
        with open(path, "wb") as f:
            f.write(data)


class RecordingController(QObject):
    recordingFinished = Signal(int, bool)  # robot_id, saved

    def __init__(self, db, mirror, parent_widget):
        super().__init__(parent_widget)
        self.db = db
        self.mirror = mirror
        self.parent = parent_widget
        self.proc: QProcess | None = None
        self._ctx: dict | None = None

    def is_running(self) -> bool:
        return self.proc is not None

    # --------------------------------------------------------------- início
    def record(self, robot_id: int, reuse_session: bool = False) -> None:
        if self.is_running():
            dialogs.info(self.parent, "Gravação em andamento",
                         "Conclua ou cancele a gravação atual antes de iniciar outra.")
            return
        robot = self.db.get_robot(robot_id)
        if robot is None:
            return

        robot_dir = self.mirror.robot_dir(robot_id)
        os.makedirs(robot_dir, exist_ok=True)
        manifest_path = os.path.join(robot_dir, "robot.json")
        session_out = os.path.join(robot_dir, "session.bin")

        # URL inicial (prefill com a do manifesto existente, se houver).
        default_url = ""
        if os.path.isfile(manifest_path):
            try:
                default_url = json.load(open(manifest_path, encoding="utf-8")).get("start_url", "")
            except (OSError, ValueError):
                pass
        start_url = dialogs.ask_text(
            self.parent, "Gravar caminho do robô",
            "URL inicial do site (deixe em branco para digitar no navegador):",
            default_url,
        )
        if start_url is None:  # usuário cancelou
            return

        steps_out = tempfile.NamedTemporaryFile(delete=False, suffix=".json").name
        session_in = session_out if (reuse_session and os.path.isfile(session_out)) else ""

        self._ctx = {
            "robot_id": robot_id,
            "name": robot.name,
            "robot_dir": robot_dir,
            "manifest_path": manifest_path,
            "session_out": session_out,
            "steps_out": steps_out,
            # Backups para o fail-safe.
            "backup_manifest": _read_bytes(manifest_path),
            "backup_session": _read_bytes(session_out),
        }

        rec_args = ["--start-url", start_url,
                    "--steps-out", steps_out,
                    "--session-out", session_out]
        if session_in:
            rec_args += ["--session-in", session_in]
        program, arguments = child_command("recorder", rec_args)

        proc = QProcess(self)
        proc.setProgram(program)
        proc.setArguments(arguments)
        proc.setWorkingDirectory(PROJECT_ROOT)
        proc.finished.connect(self._on_finished)
        proc.errorOccurred.connect(self._on_error)
        self.proc = proc
        proc.start()

    # ----------------------------------------------------------------- fim
    def _on_error(self, error):
        if self.proc is None:
            return
        if error == QProcess.FailedToStart:
            ctx = self._ctx
            self._reset()
            if ctx:
                self._restore(ctx)
                self._cleanup_temp(ctx)
            QMessageBox.warning(self.parent, "Gravação",
                                "Não foi possível iniciar o navegador de gravação.")
            if ctx:
                self.recordingFinished.emit(ctx["robot_id"], False)

    def _on_finished(self, code, _status):
        ctx = self._ctx
        self._reset()
        if ctx is None:
            return

        saved = False
        if code == 0:
            summary = None
            try:
                with open(ctx["steps_out"], encoding="utf-8") as f:
                    summary = json.load(f)
            except (OSError, ValueError):
                summary = None

            if summary is not None:
                dlg = RecordingReviewDialog(summary, ctx["name"], self.parent)
                if dlg.exec() == QDialog.Accepted:
                    manifest = dlg.build_manifest(ctx["name"])
                    manifest.save(ctx["manifest_path"])
                    self.db.update_robot(ctx["robot_id"], manifest_path=ctx["manifest_path"])
                    saved = True
                else:
                    self._restore(ctx)  # fail-safe: descartou a revisão
            else:
                self._restore(ctx)
                QMessageBox.warning(self.parent, "Gravação",
                                    "Não foi possível ler os passos gravados.")
        elif code == 2:
            self._restore(ctx)  # cancelado no navegador
        else:
            self._restore(ctx)
            QMessageBox.warning(self.parent, "Gravação",
                                "Ocorreu um erro durante a gravação.")

        self._cleanup_temp(ctx)
        self.recordingFinished.emit(ctx["robot_id"], saved)

    # ------------------------------------------------------------- helpers
    def _reset(self):
        if self.proc is not None:
            self.proc.deleteLater()
        self.proc = None
        self._ctx = None

    def _restore(self, ctx):
        _write_or_remove(ctx["manifest_path"], ctx["backup_manifest"])
        _write_or_remove(ctx["session_out"], ctx["backup_session"])

    def _cleanup_temp(self, ctx):
        try:
            if os.path.isfile(ctx["steps_out"]):
                os.remove(ctx["steps_out"])
        except OSError:
            pass
