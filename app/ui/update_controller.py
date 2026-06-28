"""Atualizador no app: verifica a release mais recente e troca o .exe.

Funciona no executável (.exe): baixa o novo .exe e usa um script PowerShell oculto
que espera ESTE processo (por PID) fechar, substitui o arquivo e reabre. Na versão
por código, apenas orienta.
"""

from __future__ import annotations

import os
import subprocess
import sys
import tempfile
import urllib.request

from PySide6.QtCore import QObject, QThread, Signal
from PySide6.QtWidgets import QApplication, QProgressDialog

from .. import updater
from . import dialogs

_CREATE_NO_WINDOW = 0x08000000  # processo sem janela de console
_CREATE_NEW_PROCESS_GROUP = subprocess.CREATE_NEW_PROCESS_GROUP


def _ps_quote(s: str) -> str:
    return "'" + str(s).replace("'", "''") + "'"


def build_update_script(pid: int, new_exe: str, target_exe: str, self_path: str = "") -> str:
    """Gera o script PowerShell que troca o executável e reabre o app.

    Espera **por PID** (este processo) terminar — e não pelo nome da imagem — para
    não confundir com outras instâncias do app (ex.: a cópia auto-instalada). Roda
    **oculto** (sem janela). Copia (com novas tentativas) em vez de mover, para não
    perder o download se o arquivo ainda estiver travado por um instante.
    """
    self_del = (f"Remove-Item -LiteralPath {_ps_quote(self_path)} -Force -ErrorAction SilentlyContinue\r\n"
                if self_path else "")
    return (
        "$ErrorActionPreference='SilentlyContinue'\r\n"
        f"$procId={int(pid)}\r\n"
        f"$new={_ps_quote(new_exe)}\r\n"
        f"$target={_ps_quote(target_exe)}\r\n"
        "for($i=0;$i -lt 150;$i++){ if(-not (Get-Process -Id $procId -ErrorAction SilentlyContinue)){break}; Start-Sleep -Milliseconds 400 }\r\n"
        "Start-Sleep -Milliseconds 500\r\n"
        "for($j=0;$j -lt 25;$j++){ try{ Copy-Item -LiteralPath $new -Destination $target -Force -ErrorAction Stop; break } catch { Start-Sleep -Milliseconds 400 } }\r\n"
        "Start-Process -FilePath $target\r\n"
        + self_del
    )


class _CheckThread(QThread):
    result = Signal(object)

    def run(self):
        self.result.emit(updater.fetch_latest())


class _DownloadThread(QThread):
    progress = Signal(int)
    done = Signal(bool, str)

    def __init__(self, url, dest, size, parent=None):
        super().__init__(parent)
        self.url, self.dest, self.size = url, dest, size

    def run(self):
        try:
            req = urllib.request.Request(self.url, headers={"User-Agent": "rpa-updater"})
            with urllib.request.urlopen(req, timeout=30) as r, open(self.dest, "wb") as f:
                total = self.size or int(r.headers.get("Content-Length", 0) or 0)
                read = 0
                while True:
                    chunk = r.read(262144)
                    if not chunk:
                        break
                    f.write(chunk)
                    read += len(chunk)
                    if total:
                        self.progress.emit(min(100, int(read * 100 / total)))
            self.done.emit(True, self.dest)
        except Exception as e:  # noqa: BLE001
            self.done.emit(False, str(e))


class UpdateController(QObject):
    availability = Signal(object)  # info dict (nova versão) ou None

    def __init__(self, parent_widget):
        super().__init__(parent_widget)
        self.parent = parent_widget
        self._latest = None
        self._check = None
        self._dl = None
        self._dlg = None

    def shutdown(self):
        """Encerra threads em andamento (ao fechar o app)."""
        for th in (self._check, self._dl):
            if th is not None and th.isRunning():
                if not th.wait(1500):
                    th.terminate()
                    th.wait(500)

    # ----------------------------------------------------- checagem silenciosa
    def check_async(self):
        self._check = _CheckThread(self)
        self._check.result.connect(self._on_check)
        self._check.start()

    def _on_check(self, info):
        self._latest = info
        if info and info.get("tag") and updater.is_newer(info["tag"]):
            self.availability.emit(info)
        else:
            self.availability.emit(None)

    # --------------------------------------------------- verificação manual
    def check_and_prompt(self):
        info = self._latest or updater.fetch_latest()
        if not info or not info.get("tag"):
            dialogs.info(self.parent, "Atualização",
                         "Não foi possível verificar atualizações (sem conexão?).")
            return
        if not updater.is_newer(info["tag"]):
            dialogs.info(self.parent, "Atualização",
                         f"Você já está na versão mais recente ({updater.APP_VERSION}).")
            return
        notes = (info.get("notes") or "").strip()
        if len(notes) > 600:
            notes = notes[:600] + "…"
        msg = (f"Nova versão {info['tag']} disponível (atual: {updater.APP_VERSION}).\n\n"
               f"{notes}\n\nBaixar e atualizar agora? O programa será reaberto.")
        if not dialogs.confirm(self.parent, "Atualizar", msg):
            return
        if not getattr(sys, "frozen", False):
            dialogs.info(self.parent, "Versão por código",
                         "Você está rodando pelo código-fonte.\n"
                         "Atualize com “git pull” ou o atalho “atualizar.bat”.")
            return
        if not info["asset_url"] or not info["asset_name"].lower().endswith(".exe"):
            dialogs.info(self.parent, "Atualização",
                         "A release mais recente não tem um .exe para baixar.")
            return
        self._start_download(info)

    def _start_download(self, info):
        dest = os.path.join(tempfile.gettempdir(), "RPA-DOWNLOAD.update.exe")
        self._dlg = QProgressDialog("Baixando atualização…", "Cancelar", 0, 100, self.parent)
        self._dlg.setWindowTitle("Atualizando")
        self._dlg.setAutoClose(False)
        self._dlg.setAutoReset(False)
        self._dlg.setValue(0)
        self._dl = _DownloadThread(info["asset_url"], dest, info.get("asset_size", 0), self)
        self._dl.progress.connect(self._dlg.setValue)
        self._dl.done.connect(self._on_downloaded)
        self._dlg.canceled.connect(self._dl.terminate)
        self._dl.start()
        self._dlg.show()

    def _on_downloaded(self, ok, path):
        if self._dlg:
            self._dlg.close()
        if not ok:
            dialogs.info(self.parent, "Atualização", f"Falha ao baixar a atualização:\n{path}")
            return
        self._apply(path)

    def _apply(self, new_exe):
        exe = sys.executable
        script = os.path.join(tempfile.gettempdir(), "rpa_update.ps1")
        content = build_update_script(os.getpid(), new_exe, exe, script)
        try:
            with open(script, "w", encoding="utf-8") as f:
                f.write(content)
            subprocess.Popen(
                ["powershell", "-NoProfile", "-NonInteractive", "-ExecutionPolicy", "Bypass",
                 "-WindowStyle", "Hidden", "-File", script],
                creationflags=_CREATE_NO_WINDOW | _CREATE_NEW_PROCESS_GROUP,
                close_fds=True,
            )
        except Exception as e:  # noqa: BLE001
            dialogs.info(self.parent, "Atualização", f"Não foi possível iniciar a troca:\n{e}")
            return
        QApplication.quit()
