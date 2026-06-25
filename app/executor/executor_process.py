"""Subprocesso de execução de um robô.

Roda o manifesto em Chromium headless ("execução invisível"). Se detectar sessão
expirada (campo de senha visível ao abrir o site), abre o navegador na tela para
o usuário logar manualmente, recaptura/salva a sessão e retoma a execução.

Comunicação com o app (stdout, uma linha JSON por evento):
    {"type":"log","msg":...}
    {"type":"login_required"}
    {"type":"done","ok":true|false,"downloads":[...],"error":""}

Códigos de saída: 0 = sucesso, 2 = cancelado, 3 = erro.
"""

from __future__ import annotations

import argparse
import json
import os
import sys

try:
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:
    pass

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from playwright.sync_api import sync_playwright  # noqa: E402

from app.executor.browser import ensure_chromium  # noqa: E402
from app.executor.executor_core import ExecutionEngine, has_visible_password  # noqa: E402
from app.robot_manifest import RobotManifest  # noqa: E402
from app.services import crypto  # noqa: E402

EXIT_OK = 0
EXIT_CANCEL = 2
EXIT_ERROR = 3

_LOGIN_OVERLAY_JS = r"""
(() => {
  if (window.__rpa_login_installed || window.top !== window.self) return;
  window.__rpa_login_installed = true;
  function build() {
    if (document.getElementById('__rpa_login_bar')) return;
    const bar = document.createElement('div');
    bar.id = '__rpa_login_bar';
    bar.style.cssText = 'position:fixed;top:12px;left:50%;transform:translateX(-50%);' +
      'z-index:2147483647;background:#161619;color:#F2E9CE;border:1px solid #D4AF37;' +
      'border-radius:10px;padding:10px 14px;font-family:Segoe UI,Arial,sans-serif;' +
      'font-size:13px;box-shadow:0 6px 20px rgba(0,0,0,.4);display:flex;gap:10px;align-items:center;';
    const msg = document.createElement('span');
    msg.textContent = 'Sessão expirada — faça login normalmente. Ao terminar, clique:';
    const btn = document.createElement('button');
    btn.textContent = '✔ Já fiz login, continuar';
    btn.style.cssText = 'background:#D4AF37;color:#161619;border:none;border-radius:8px;' +
      'padding:6px 12px;font-weight:700;cursor:pointer;';
    btn.onclick = () => { if (window.__rpa_login_done) window.__rpa_login_done(); };
    bar.appendChild(msg); bar.appendChild(btn);
    (document.body || document.documentElement).appendChild(bar);
  }
  if (document.readyState === 'loading')
    document.addEventListener('DOMContentLoaded', build);
  else build();
  setInterval(build, 1000);
})();
"""


def _emit(obj):
    try:
        if sys.stdout is not None:
            sys.stdout.write(json.dumps(obj, ensure_ascii=False) + "\n")
            sys.stdout.flush()
    except (OSError, ValueError):
        pass


def _make_context(browser, session_path):
    kwargs = {"accept_downloads": True}
    if session_path and os.path.isfile(session_path):
        try:
            kwargs["storage_state"] = json.loads(crypto.load_text_encrypted(session_path))
        except (OSError, ValueError):
            pass
    return browser.new_context(**kwargs)


def _run_headless(pw, manifest, start_url, download_dir, session_path, log):
    browser = pw.chromium.launch(headless=True)
    try:
        ctx = _make_context(browser, session_path)
        page = ctx.new_page()
        try:
            page.goto(start_url, wait_until="domcontentloaded", timeout=30000)
        except Exception:
            pass
        if has_visible_password(page):
            return "needs_login", []
        engine = ExecutionEngine(page, manifest, download_dir, log=log)
        res = engine.execute()
        return ("ok" if res.ok else "error"), res.downloads
    finally:
        browser.close()


def _manual_login(pw, start_url, session_path, log):
    log("Abrindo navegador para login manual…")
    browser = pw.chromium.launch(headless=False)
    try:
        ctx = _make_context(browser, session_path)
        done = {"v": False}
        ctx.expose_binding("__rpa_login_done", lambda *_: done.__setitem__("v", True))
        ctx.add_init_script(_LOGIN_OVERLAY_JS)
        page = ctx.new_page()
        page.on("close", lambda *_: done.__setitem__("v", "closed"))
        try:
            page.goto(start_url, wait_until="domcontentloaded", timeout=60000)
        except Exception:
            pass
        while done["v"] is False:
            try:
                page.wait_for_timeout(200)
            except Exception:
                done["v"] = "closed"
        if done["v"] == "closed":
            return False
        state = ctx.storage_state()
        crypto.save_text_encrypted(session_path, json.dumps(state))
        log("Sessão recapturada e salva.")
        return True
    finally:
        browser.close()


def _parse(argv):
    p = argparse.ArgumentParser(description="Executor de robô (Playwright).")
    p.add_argument("--manifest", required=True)
    p.add_argument("--download-dir", required=True)
    p.add_argument("--session-in", default="")
    p.add_argument("--start-url", default="")
    p.add_argument("--log", default="")
    return p.parse_args(argv)


def main(argv=None) -> int:
    args = _parse(argv if argv is not None else sys.argv[1:])
    manifest = RobotManifest.load(args.manifest)
    start_url = args.start_url or manifest.start_url
    session_path = args.session_in

    logf = open(args.log, "a", encoding="utf-8") if args.log else None

    def log(msg):
        _emit({"type": "log", "msg": msg})
        if logf:
            logf.write(msg + "\n")
            logf.flush()

    rc = EXIT_ERROR
    downloads = []
    error = ""
    try:
        ensure_chromium(log)  # baixa o navegador no 1º uso, se necessário
        with sync_playwright() as pw:
            status, downloads = _run_headless(pw, manifest, start_url,
                                              args.download_dir, session_path, log)
            if status == "needs_login":
                _emit({"type": "login_required"})
                if _manual_login(pw, start_url, session_path, log):
                    status, downloads = _run_headless(pw, manifest, start_url,
                                                      args.download_dir, session_path, log)
                else:
                    status = "cancel"

            if status == "ok":
                rc = EXIT_OK
            elif status == "cancel":
                rc = EXIT_CANCEL
            else:
                rc = EXIT_ERROR
                error = "Falha na execução (ver log)."
    except Exception as e:  # nunca derruba sem reportar
        error = f"{type(e).__name__}: {e}"
        log("ERRO: " + error)
        rc = EXIT_ERROR
    finally:
        if logf:
            logf.close()

    _emit({"type": "done", "ok": rc == EXIT_OK, "downloads": downloads, "error": error})
    return rc


if __name__ == "__main__":
    sys.exit(main())
