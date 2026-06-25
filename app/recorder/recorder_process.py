"""Subprocesso do gravador.

Abre o Chromium (headed) controlado pelo Playwright, injeta o recorder.js e
acumula as ações via RecordingSession. Ao concluir, salva os passos em
``--steps-out`` e o storage_state criptografado em ``--session-out`` e sai com
código 0. Ao cancelar (ou fechar a janela), sai com código 2 e NADA é salvo
(fail-safe).

Execução típica (pelo app):
    python -m app.recorder.recorder_process --start-url URL \
        --steps-out steps.json --session-out session.bin
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import time

# Garante que o pacote "app" seja importável quando rodado como script solto.
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from playwright.sync_api import sync_playwright  # noqa: E402

from app.executor.browser import ensure_chromium  # noqa: E402
from app.recorder.recorder_core import RecordingSession  # noqa: E402
from app.services import crypto  # noqa: E402

EXIT_OK = 0
EXIT_CANCEL = 2
EXIT_ERROR = 3


def _parse_args(argv):
    p = argparse.ArgumentParser(description="Gravador de robô (Playwright).")
    p.add_argument("--start-url", default="")
    p.add_argument("--steps-out", required=True)
    p.add_argument("--session-out", required=True)
    p.add_argument("--session-in", default="")
    p.add_argument("--headless", action="store_true")
    p.add_argument("--auto-finish-ms", type=int, default=0,
                   help="(testes) conclui automaticamente após N ms.")
    return p.parse_args(argv)


def _set_cancel(session):
    if not session.finished:
        session.result = "cancel"
        session.finished = True


def main(argv=None) -> int:
    args = _parse_args(argv if argv is not None else sys.argv[1:])

    ensure_chromium()  # baixa o navegador no 1º uso, se necessário

    with sync_playwright() as pw:
        browser = pw.chromium.launch(headless=args.headless, args=["--start-maximized"])
        # no_viewport: o site ocupa a janela inteira (sem a margem cinza do
        # viewport fixo padrão do Playwright).
        ctx_kwargs = {"accept_downloads": True, "no_viewport": True}
        if args.session_in and os.path.isfile(args.session_in):
            try:
                ctx_kwargs["storage_state"] = json.loads(
                    crypto.load_text_encrypted(args.session_in)
                )
            except (OSError, ValueError):
                pass

        context = browser.new_context(**ctx_kwargs)
        page = context.new_page()
        session = RecordingSession(start_url=args.start_url)
        session.attach(context, page)
        page.on("close", lambda *_: _set_cancel(session))
        context.on("close", lambda *_: _set_cancel(session))

        try:
            page.goto(args.start_url or "about:blank")
        except Exception:
            pass

        started = time.monotonic()
        while not session.finished:
            try:
                page.wait_for_timeout(200)
            except Exception:
                _set_cancel(session)
                break
            if args.auto_finish_ms and (time.monotonic() - started) * 1000 >= args.auto_finish_ms:
                session._on_control(None, "finish")

        rc = EXIT_ERROR
        if session.result == "ok":
            try:
                summary, state = session.build_result()
                os.makedirs(os.path.dirname(os.path.abspath(args.steps_out)), exist_ok=True)
                with open(args.steps_out, "w", encoding="utf-8") as f:
                    json.dump(summary, f, ensure_ascii=False, indent=2)
                crypto.save_text_encrypted(args.session_out, json.dumps(state))
                rc = EXIT_OK
            except Exception:
                rc = EXIT_ERROR
        else:
            rc = EXIT_CANCEL

        try:
            context.close()
            browser.close()
        except Exception:
            pass
        return rc


if __name__ == "__main__":
    sys.exit(main())
