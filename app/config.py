"""Configuração da aplicação e gestão da primeira execução.

O config.json (que aponta para o diretório raiz escolhido pelo usuário e o tema)
fica em %LOCALAPPDATA%/RPADownload. Os dados em si (pastas espelhadas + banco)
ficam dentro de "<raiz escolhida>/RPA-DOWNLOAD".
"""

from __future__ import annotations

import json
import os

APP_DISPLAY_NAME = "RPA Download"
APP_FOLDER_NAME = "RPA-DOWNLOAD"
ORG_NAME = "RPADownload"
DEFAULT_THEME = "dark"


def _config_dir() -> str:
    # Override opcional (usado em testes para não tocar na config real do usuário).
    override = os.environ.get("RPA_CONFIG_DIR")
    if override:
        return override
    base = os.environ.get("LOCALAPPDATA") or os.path.expanduser("~")
    return os.path.join(base, ORG_NAME)


def config_file() -> str:
    return os.path.join(_config_dir(), "config.json")


def load_config() -> dict:
    path = config_file()
    if os.path.isfile(path):
        try:
            with open(path, "r", encoding="utf-8") as f:
                return json.load(f)
        except (OSError, ValueError):
            return {}
    return {}


def save_config(cfg: dict) -> None:
    os.makedirs(_config_dir(), exist_ok=True)
    with open(config_file(), "w", encoding="utf-8") as f:
        json.dump(cfg, f, indent=2, ensure_ascii=False)


def get_data_root() -> str | None:
    """Retorna o caminho da pasta de dados ('...AUTOMATIZADOR...') ou None."""
    root = load_config().get("data_root")
    if root and os.path.isdir(root):
        return root
    return None


def initialize_root(parent_dir: str) -> str:
    """Cria a pasta da aplicação dentro de ``parent_dir`` e persiste no config."""
    data_root = os.path.join(parent_dir, APP_FOLDER_NAME)
    os.makedirs(data_root, exist_ok=True)
    cfg = load_config()
    cfg["data_root"] = data_root
    save_config(cfg)
    return data_root


def db_path(data_root: str) -> str:
    return os.path.join(data_root, ".rpa", "app.db")


def get_theme() -> str:
    return load_config().get("theme", DEFAULT_THEME)


def set_theme(theme: str) -> None:
    cfg = load_config()
    cfg["theme"] = theme
    save_config(cfg)


def get_execution_headed() -> bool:
    """True = navegador visível durante a execução (padrão)."""
    return bool(load_config().get("execution_headed", True))


def set_execution_headed(value: bool) -> None:
    cfg = load_config()
    cfg["execution_headed"] = bool(value)
    save_config(cfg)
