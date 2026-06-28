"""Verificação de atualização baseada nas Releases do GitHub (repo público)."""

from __future__ import annotations

import json
import re
import urllib.request

from app import __version__ as APP_VERSION

REPO = "victoraalm/rpa-download"
_API_LATEST = f"https://api.github.com/repos/{REPO}/releases/latest"


def _ver(s: str) -> tuple:
    nums = re.findall(r"\d+", s or "")
    return tuple(int(x) for x in (nums + ["0", "0", "0"])[:3])


def fetch_latest(timeout: float = 8.0) -> dict | None:
    """Retorna info da release mais recente, ou None se não der para verificar."""
    req = urllib.request.Request(_API_LATEST, headers={
        "User-Agent": "rpa-updater",
        "Accept": "application/vnd.github+json",
    })
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            data = json.load(r)
    except Exception:
        return None
    assets = data.get("assets", []) or []
    # Distribuição em .zip (modo pasta). Mantém fallback p/ .exe (compatibilidade).
    zip_ = next((a for a in assets if a.get("name", "").lower().endswith(".zip")), None)
    chosen = zip_ or next((a for a in assets if a.get("name", "").lower().endswith(".exe")), None)
    return {
        "tag": data.get("tag_name", ""),
        "title": data.get("name", ""),
        "notes": data.get("body", "") or "",
        "asset_url": (chosen or {}).get("browser_download_url", ""),
        "asset_name": (chosen or {}).get("name", ""),
        "asset_size": (chosen or {}).get("size", 0),
    }


def is_newer(tag: str, current: str = APP_VERSION) -> bool:
    return _ver(tag) > _ver(current)
