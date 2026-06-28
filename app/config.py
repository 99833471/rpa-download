"""Configuração da aplicação.

O config.json (tema, preferências e o caminho da pasta de dados) fica em
%LOCALAPPDATA%/RPADownload. A pasta de dados (banco, robôs, downloads, sessões) é
criada **automaticamente** em %LOCALAPPDATA%/RPA Download — sem pedir caminho ao
usuário e sem exigir admin; fora do OneDrive (evita locks). O .exe se instala em
%LOCALAPPDATA%/Programs/RPA Download (ver app/installer.py).
"""

from __future__ import annotations

import json
import os
import shutil

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


def install_dir() -> str:
    """Pasta de instalação do .exe (por usuário, sem admin)."""
    base = os.environ.get("LOCALAPPDATA") or os.path.expanduser("~")
    return os.path.join(base, "Programs", APP_DISPLAY_NAME)


def default_data_root() -> str:
    """Melhor local para a pasta de dados: sem admin e fora do OneDrive."""
    override = os.environ.get("RPA_DATA_ROOT")  # usado em testes/validação
    if override:
        return override
    base = os.environ.get("LOCALAPPDATA") or os.path.expanduser("~")
    return os.path.join(base, APP_DISPLAY_NAME)


def _same_path(a: str, b: str) -> bool:
    return os.path.normcase(os.path.normpath(a)) == os.path.normcase(os.path.normpath(b))


def _migrate_data(old: str, new: str) -> None:
    """Move o conteúdo de uma pasta de dados antiga para a nova (best-effort)."""
    try:
        os.makedirs(new, exist_ok=True)
        for entry in os.listdir(old):
            src = os.path.join(old, entry)
            dst = os.path.join(new, entry)
            if os.path.exists(dst):
                continue  # não sobrescreve o que já existe no destino
            try:
                shutil.move(src, dst)
            except OSError:
                pass
    except OSError:
        pass


def ensure_data_root() -> str:
    """Garante a pasta de dados no local padrão (criando-a) e a persiste. Se uma
    versão anterior gravou um caminho diferente (escolhido pelo usuário), migra os
    dados de lá para o novo local."""
    default = default_data_root()
    cfg = load_config()
    old = cfg.get("data_root")
    if old and os.path.isdir(old) and not _same_path(old, default):
        _migrate_data(old, default)
    os.makedirs(default, exist_ok=True)
    if cfg.get("data_root") != default:
        cfg["data_root"] = default
        save_config(cfg)
    return default


def initialize_root(parent_dir: str) -> str:
    """Cria a pasta da aplicação dentro de ``parent_dir`` e persiste no config.
    (Mantido por compatibilidade; o fluxo atual usa ``ensure_data_root``.)"""
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


def get_log_retention_days() -> int:
    """Dias para manter os logs de execução (runs/). 0 = nunca apagar."""
    try:
        return int(load_config().get("log_retention_days", 30))
    except (TypeError, ValueError):
        return 30


def set_log_retention_days(days: int) -> None:
    cfg = load_config()
    cfg["log_retention_days"] = int(days)
    save_config(cfg)


def get_execution_headed() -> bool:
    """True = navegador visível durante a execução (padrão)."""
    return bool(load_config().get("execution_headed", True))


def set_execution_headed(value: bool) -> None:
    cfg = load_config()
    cfg["execution_headed"] = bool(value)
    save_config(cfg)
