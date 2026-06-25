"""Garante o navegador (Chromium) do Playwright — baixa no 1º uso se faltar.

Usado tanto pelo app empacotado (.exe) quanto pelo runner por robô. O download
vai para PLAYWRIGHT_BROWSERS_PATH (definido na inicialização para um local
estável e gravável do usuário).
"""

from __future__ import annotations

import subprocess


def ensure_chromium(log=print) -> bool:
    """Retorna True se o Chromium está pronto para uso."""
    from playwright.sync_api import sync_playwright
    try:
        with sync_playwright() as pw:
            browser = pw.chromium.launch(headless=True)
            browser.close()
        return True
    except Exception:
        log("Baixando o navegador (Chromium) na primeira execução — aguarde…")

    try:
        from playwright._impl._driver import compute_driver_executable, get_driver_env
        exe = compute_driver_executable()
        cmd = list(exe) if isinstance(exe, (list, tuple)) else [exe]
        subprocess.run([*cmd, "install", "chromium"], env=get_driver_env(), check=False)
        # Confirma que ficou utilizável.
        with sync_playwright() as pw:
            browser = pw.chromium.launch(headless=True)
            browser.close()
        return True
    except Exception as e:
        log(f"Falha ao preparar o navegador: {e}")
        return False
