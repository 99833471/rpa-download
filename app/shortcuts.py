"""Cria atalhos do Windows: na pasta Documentos e no Menu Iniciar.

O atalho no Menu Iniciar é o que torna o programa **pesquisável** no Windows
(digitar "RPA Download" no menu Iniciar passa a encontrá-lo).

Os atalhos (.lnk) são criados via WScript.Shell (PowerShell), sem dependências
extras — funciona no executável empacotado. Tudo é silencioso/best-effort.
"""

from __future__ import annotations

import os
import subprocess

SHORTCUT_NAME = "RPA Download.lnk"
_CREATE_NO_WINDOW = 0x08000000


def _ps_quote(s: str) -> str:
    return "'" + str(s).replace("'", "''") + "'"


def _create_shortcut(lnk_path: str, target: str, workdir: str,
                     description: str = "RPA Download") -> bool:
    ps = (
        "$ws = New-Object -ComObject WScript.Shell; "
        f"$s = $ws.CreateShortcut({_ps_quote(lnk_path)}); "
        f"$s.TargetPath = {_ps_quote(target)}; "
        f"$s.WorkingDirectory = {_ps_quote(workdir)}; "
        f"$s.IconLocation = {_ps_quote(target + ',0')}; "
        f"$s.Description = {_ps_quote(description)}; "
        "$s.Save()"
    )
    try:
        r = subprocess.run(
            ["powershell", "-NoProfile", "-NonInteractive", "-Command", ps],
            creationflags=_CREATE_NO_WINDOW,
            capture_output=True, timeout=30,
        )
        return r.returncode == 0 and os.path.isfile(lnk_path)
    except Exception:
        return False


def documents_dir() -> str | None:
    """Pasta Documentos do usuário (respeita redirecionamento p/ OneDrive)."""
    override = os.environ.get("RPA_DOCUMENTS_DIR")  # usado em testes (hermético)
    if override:
        return override
    try:
        import winreg
        with winreg.OpenKey(
            winreg.HKEY_CURRENT_USER,
            r"Software\Microsoft\Windows\CurrentVersion\Explorer\User Shell Folders",
        ) as key:
            val, _ = winreg.QueryValueEx(key, "Personal")
            path = os.path.expandvars(val)
            if path and os.path.isdir(path):
                return path
    except OSError:
        pass
    fallback = os.path.join(os.path.expanduser("~"), "Documents")
    return fallback if os.path.isdir(fallback) else None


def start_menu_programs_dir() -> str | None:
    appdata = os.environ.get("APPDATA")
    if not appdata:
        return None
    return os.path.join(appdata, "Microsoft", "Windows", "Start Menu", "Programs")


def ensure_shortcuts(exe: str, config_module=None) -> None:
    """Garante os atalhos. Menu Iniciar: recria se faltar (mantém pesquisável).
    Documentos: cria só uma vez (respeita exclusão posterior pelo usuário).
    """
    if os.name != "nt" or not exe:
        return
    workdir = os.path.dirname(exe)

    # Menu Iniciar (pesquisável) — cria se não existir.
    programs = start_menu_programs_dir()
    if programs:
        try:
            os.makedirs(programs, exist_ok=True)
            sm_lnk = os.path.join(programs, SHORTCUT_NAME)
            if not os.path.isfile(sm_lnk):
                _create_shortcut(sm_lnk, exe, workdir)
        except OSError:
            pass

    # Documentos — cria uma vez (flag em config).
    docs = documents_dir()
    if docs and config_module is not None:
        try:
            cfg = config_module.load_config()
            if not cfg.get("doc_shortcut_done"):
                if _create_shortcut(os.path.join(docs, SHORTCUT_NAME), exe, workdir):
                    cfg["doc_shortcut_done"] = True
                    config_module.save_config(cfg)
        except Exception:
            pass
