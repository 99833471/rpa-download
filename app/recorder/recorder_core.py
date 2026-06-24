"""Núcleo testável da gravação.

A classe RecordingSession liga os bindings/handlers a um contexto+página do
Playwright e acumula os passos brutos (cliques, fills, selects, navegações,
downloads). É independente de UI e de subprocesso, o que permite testá-la
dirigindo eventos por código (ver tests/recorder_session_test.py).
"""

from __future__ import annotations

import json
import os
import time

RECORDER_JS_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "recorder.js")
# Navegações que ocorrem até este intervalo após uma ação são tratadas como
# efeito de um clique já gravado (não viram passo 'goto' duplicado).
_NAV_DEBOUNCE_S = 1.5


def load_recorder_js() -> str:
    with open(RECORDER_JS_PATH, "r", encoding="utf-8") as f:
        return f.read()


class RecordingSession:
    def __init__(self, start_url: str = ""):
        self.start_url = start_url
        self.steps: list[dict] = []
        self.result: str | None = None      # 'ok' | 'cancel'
        self.finished = False
        self._last_action = 0.0
        self._context = None
        self._page = None

    # ------------------------------------------------------------- ligação
    def attach(self, context, page) -> None:
        self._context = context
        self._page = page
        context.expose_binding("__rpa_record", self._on_record)
        context.expose_binding("__rpa_control", self._on_control)
        context.add_init_script(load_recorder_js())
        page.on("framenavigated", self._on_nav)
        context.on("download", self._on_download)

    def _touch(self) -> None:
        self._last_action = time.monotonic()

    # ------------------------------------------------------------ handlers
    def _on_record(self, source, arg) -> None:
        try:
            data = json.loads(arg)
        except (ValueError, TypeError):
            return
        if isinstance(data, dict) and data.get("action"):
            self.steps.append(data)
            self._touch()

    def _on_control(self, source, action) -> None:
        if action == "finish":
            self.result = "ok"
            self.finished = True
        elif action == "cancel":
            self.result = "cancel"
            self.finished = True

    def _on_nav(self, frame) -> None:
        try:
            if self._page is None or frame != self._page.main_frame:
                return
            url = frame.url or ""
        except Exception:
            return
        if not url or url == "about:blank":
            return
        # Ignora navegações que são consequência de um clique recém-gravado.
        if time.monotonic() - self._last_action < _NAV_DEBOUNCE_S:
            return
        if self.steps and self.steps[-1].get("action") == "goto" and self.steps[-1].get("url") == url:
            return
        self.steps.append({"action": "goto", "url": url, "selectors": []})
        self._touch()

    def _on_download(self, download) -> None:
        try:
            name = download.suggested_filename or ""
        except Exception:
            name = ""
        self.steps.append({"action": "download", "selectors": [], "value": name})

    # -------------------------------------------------------------- saída
    def build_result(self) -> tuple[dict, dict]:
        """Retorna (resumo_dos_passos, storage_state)."""
        state = self._context.storage_state() if self._context else {}
        has_login = bool(state.get("cookies")) or any(
            o.get("localStorage") for o in state.get("origins", [])
        )
        summary = {
            "start_url": self.start_url,
            "has_login": has_login,
            "steps": self.steps,
        }
        return summary, state
