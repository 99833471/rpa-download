"""Núcleo da execução — independente de UI e de subprocesso (testável headless).

Executa os passos de um RobotManifest com as redundâncias exigidas:
- Smart waits (nativo do Playwright: espera visível/clicável; sem sleep fixo).
- Auto-retry com backoff exponencial (até 3 tentativas por ação).
- Evasão de pop-ups (fecha banners de cookies/avisos e refaz a ação).
- Fallback de seletor (tenta cada candidato: id -> ... -> XPath).
- Download: captura, valida integridade (0 bytes/corrompido -> refaz) e nomeia
  como "[timestamp] - [nome]" (exceção: nome que já tem timestamp por regex).

Os valores dos campos já chegam resolvidos no manifesto (field.value), pois o
app resolve fórmulas e perguntas Manual antes de iniciar.
"""

from __future__ import annotations

import os
import re
import time
from dataclasses import dataclass, field
from datetime import datetime

from playwright.sync_api import Error as PWError
from playwright.sync_api import TimeoutError as PWTimeout

from .. import formula
from ..robot_manifest import RobotManifest
from .partition import partition_plan

# Textos comuns de botões que fecham pop-ups/banners.
_CLOSE_LABELS = [
    "Aceitar todos", "Aceitar tudo", "Aceitar", "Aceito", "Concordo", "Continuar",
    "Entendi", "Got it", "Accept all", "Accept", "OK", "Ok", "Fechar", "Close",
    "Dispensar", "Dismiss", "✕", "×", "X",
]
_CLOSE_SELECTORS = [
    '[aria-label="Fechar"]', '[aria-label="Close"]', '[aria-label="fechar"]',
    "button.close", ".close-button", ".modal-close", "#onetrust-accept-btn-handler",
    ".cookie-accept", ".cc-allow", ".cc-dismiss",
]

# Detecta um carimbo de data/hora já presente no nome do arquivo.
_TIMESTAMP_RE = re.compile(
    r"(19|20)\d{2}[-_.]?\d{2}[-_.]?\d{2}([-_. ]?\d{2}[-_.:]?\d{2})?|\d{8}|\d{10,}"
)


def has_timestamp(name: str) -> bool:
    base = os.path.splitext(name)[0]
    return bool(_TIMESTAMP_RE.search(base))


def timestamp_filename(name: str, now: datetime | None = None) -> str:
    name = name or "download"
    if has_timestamp(name):
        return name
    ts = (now or datetime.now()).strftime("%Y-%m-%d_%H-%M-%S")
    return f"{ts} - {name}"


@dataclass
class RunResult:
    ok: bool
    error: str = ""
    downloads: list = field(default_factory=list)


class ExecutionError(Exception):
    pass


def has_visible_password(page) -> bool:
    """Heurística de sessão expirada: existe um campo de senha visível?"""
    try:
        loc = page.locator("input[type='password']")
        n = loc.count()
        for i in range(min(n, 5)):
            if loc.nth(i).is_visible():
                return True
    except PWError:
        pass
    return False


class ExecutionEngine:
    def __init__(self, page, manifest: RobotManifest, download_dir: str,
                 log=None, *, action_timeout=8000, download_timeout=30000,
                 max_attempts=3, backoff_base=0.5, partition_download_timeout=6000):
        self.page = page
        self.manifest = manifest
        self.download_dir = download_dir
        self.log = log or (lambda msg: None)
        self.action_timeout = action_timeout
        self.download_timeout = download_timeout
        self.max_attempts = max_attempts
        self.backoff_base = backoff_base
        # Timeout curto usado ao testar um intervalo no particionamento (falha rápida
        # = site recusou por limite, hora de dividir).
        self.partition_download_timeout = partition_download_timeout
        self._partition_downloads: list = []

    # ------------------------------------------------------------- entrada
    def execute(self) -> RunResult:
        """Ponto de entrada: aplica particionamento adaptativo se o site tem limite."""
        lim = self.manifest.site_limit
        if lim and lim.enabled and lim.strategy == "date_partition" and self._valid_date_steps(lim):
            return self._run_partitioned(lim)
        return self.run()

    # ----------------------------------------------------------------- run
    def run(self, overrides: dict | None = None) -> RunResult:
        os.makedirs(self.download_dir, exist_ok=True)
        downloads = []
        steps = self.manifest.steps
        i = 0
        while i < len(steps):
            step = steps[i]
            nxt = steps[i + 1] if i + 1 < len(steps) else None
            self.log(f"Passo {i}: {step.action} {step.label or step.url or ''}".strip())
            try:
                if step.action == "goto":
                    self._goto(step)
                elif step.action == "click":
                    if nxt is not None and nxt.action == "download":
                        downloads.append(self._click_download(step))
                        i += 1  # consome o marcador de download
                    else:
                        self._click(step)
                elif step.action == "fill":
                    self._fill(step, self._value_for(step, overrides, i))
                elif step.action == "select":
                    self._select(step, self._value_for(step, overrides, i))
                elif step.action == "press":
                    self._press(step)
                elif step.action == "download":
                    self.log("  (marcador de download sem clique associado — ignorado)")
            except ExecutionError as e:
                self.log(f"ERRO no passo {i}: {e}")
                return RunResult(False, str(e), downloads)
            i += 1
        self.log(f"Concluído. {len(downloads)} arquivo(s) baixado(s).")
        return RunResult(True, "", downloads)

    @staticmethod
    def _value_for(step, overrides, i):
        if overrides and i in overrides:
            return overrides[i]
        return step.field.value if step.field else step.value

    # ------------------------------------------------------- particionamento
    def _valid_date_steps(self, lim) -> bool:
        n = len(self.manifest.steps)
        for idx in (lim.start_date_step, lim.end_date_step):
            if not (0 <= idx < n):
                return False
            st = self.manifest.steps[idx]
            if st.action not in ("fill", "select") or st.field is None:
                return False
        return True

    def _run_partitioned(self, lim) -> RunResult:
        os.makedirs(self.download_dir, exist_ok=True)
        fmt = self.manifest.steps[lim.start_date_step].field.fmt or "dd/mm/yyyy"
        try:
            s = formula.parse_date(self.manifest.steps[lim.start_date_step].field.value, fmt)
            e = formula.parse_date(self.manifest.steps[lim.end_date_step].field.value, fmt)
        except (ValueError, AttributeError) as ex:
            self.log(f"Datas inválidas para particionamento ({ex}); executando sem particionar.")
            return self.run()
        self.log(f"Limite do site ativo — particionando intervalo "
                 f"{formula.format_date(s, fmt)} a {formula.format_date(e, fmt)}…")
        self._partition_downloads = []
        succeeded, failed = partition_plan(s, e, lambda a, b: self._attempt_range(lim, fmt, a, b))
        downloads = self._partition_downloads
        if failed and not succeeded:
            return RunResult(False, "O site não liberou o download em nenhum período.", downloads)
        if failed:
            return RunResult(True, f"{len(failed)} período(s) não liberaram o download.", downloads)
        self.log(f"Particionamento concluído: {len(downloads)} arquivo(s) em "
                 f"{len(succeeded)} período(s).")
        return RunResult(True, "", downloads)

    def _attempt_range(self, lim, fmt, a, b) -> bool:
        overrides = {
            lim.start_date_step: formula.format_date(a, fmt),
            lim.end_date_step: formula.format_date(b, fmt),
        }
        self.log(f"  testando período {formula.format_date(a, fmt)} a {formula.format_date(b, fmt)}")
        # Falha rápida para detectar o limite (sem retries longos de download).
        prev_to, prev_att = self.download_timeout, self.max_attempts
        self.download_timeout, self.max_attempts = self.partition_download_timeout, 1
        try:
            res = self.run(overrides=overrides)
        finally:
            self.download_timeout, self.max_attempts = prev_to, prev_att
        if res.ok and res.downloads:
            self._partition_downloads.extend(res.downloads)
            return True
        return False

    # ------------------------------------------------------------- helpers
    def _locator(self, selector):
        t = selector.type
        if t == "xpath":
            return self.page.locator("xpath=" + selector.value)
        if t == "text":
            return self.page.get_by_text(selector.value, exact=False)
        return self.page.locator(selector.value)  # id | css

    def _attempt(self, fn, what):
        last = None
        for k in range(self.max_attempts):
            try:
                return fn()
            except (PWError, PWTimeout) as e:
                last = e
                self.log(f"  tentativa {k + 1}/{self.max_attempts} falhou ({what}): "
                         f"{type(e).__name__}")
                if self._evade_popups():
                    self.log("  pop-up detectado e fechado; refazendo ação…")
                    continue
                if k < self.max_attempts - 1:
                    time.sleep(self.backoff_base * (2 ** k))  # backoff exponencial
        raise ExecutionError(f"{what}: {last}")

    def _over_selectors(self, step, do, what):
        if not step.selectors:
            raise ExecutionError(f"{what}: passo sem seletores")
        last = None
        for sel in step.selectors:
            loc = self._locator(sel)
            try:
                return self._attempt(lambda l=loc: do(l), f"{what} [{sel.type}]")
            except ExecutionError as e:
                last = e
                self.log(f"  seletor {sel.type} esgotado; tentando próximo…")
        raise last or ExecutionError(f"{what}: nenhum seletor funcionou")

    def _goto(self, step):
        self._attempt(
            lambda: self.page.goto(step.url, wait_until="domcontentloaded",
                                   timeout=self.download_timeout),
            "navegar",
        )

    def _click(self, step):
        self._over_selectors(step, lambda l: l.first.click(timeout=self.action_timeout), "clique")

    def _fill(self, step, value):
        self._over_selectors(
            step, lambda l: l.first.fill(value, timeout=self.action_timeout), "preencher"
        )

    def _select(self, step, value):
        def do(l):
            try:
                l.first.select_option(value=value, timeout=self.action_timeout)
            except (PWError, PWTimeout):
                l.first.select_option(label=value, timeout=self.action_timeout)
        self._over_selectors(step, do, "selecionar")

    def _press(self, step):
        key = step.value or "Enter"
        self._over_selectors(
            step, lambda l: l.first.press(key, timeout=self.action_timeout), "tecla"
        )

    def _click_download(self, step) -> str:
        def do(l):
            with self.page.expect_download(timeout=self.download_timeout) as info:
                l.first.click(timeout=self.action_timeout)
            dl = info.value
            name = timestamp_filename(dl.suggested_filename or "download")
            dest = os.path.join(self.download_dir, name)
            dl.save_as(dest)
            # Validação de integridade.
            if not os.path.exists(dest) or os.path.getsize(dest) == 0:
                try:
                    os.remove(dest)
                except OSError:
                    pass
                raise PWError("arquivo baixado vazio/corrompido")
            self.log(f"  download salvo: {name}")
            return dest
        return self._over_selectors(step, do, "download")

    def _evade_popups(self) -> bool:
        # Tenta botões por texto (role=button e links).
        for label in _CLOSE_LABELS:
            try:
                btn = self.page.get_by_role("button", name=label, exact=False)
                if btn.count() and btn.first.is_visible():
                    btn.first.click(timeout=1200)
                    return True
            except (PWError, PWTimeout):
                pass
        # Tenta seletores comuns de fechamento.
        for css in _CLOSE_SELECTORS:
            try:
                el = self.page.locator(css)
                if el.count() and el.first.is_visible():
                    el.first.click(timeout=1200)
                    return True
            except (PWError, PWTimeout):
                pass
        return False
