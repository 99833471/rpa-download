"""Testa a escolha automática da pasta de dados e a migração de dados antigos.

Valida, sem interação manual:
- default_data_root respeita o override RPA_DATA_ROOT.
- ensure_data_root cria a pasta no local padrão e persiste no config.
- ensure_data_root migra o conteúdo de uma pasta antiga (escolhida em versões
  anteriores) para o novo local, sem sobrescrever o que já existe no destino.

Uso:  python tests/install_test.py
"""

from __future__ import annotations

import os
import sys
import tempfile

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

_failures = []


def check(label, cond):
    print(f"  [{'OK ' if cond else 'FALHOU'}] {label}")
    if not cond:
        _failures.append(label)


def _write(path, text):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        f.write(text)


def main():
    print("== Pasta automática + migração ==")
    with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as base:
        cfg_dir = os.path.join(base, "cfg")
        new_root = os.path.join(base, "novo", "RPA Download")
        old_root = os.path.join(base, "antigo", "RPA-DOWNLOAD")

        # Isola a config e força o local padrão para um caminho de teste.
        os.environ["RPA_CONFIG_DIR"] = cfg_dir
        os.environ["RPA_DATA_ROOT"] = new_root

        import importlib

        from app import config as config  # noqa: E402
        importlib.reload(config)

        check("default_data_root respeita override", config.default_data_root() == new_root)

        # Simula uma instalação antiga: config aponta p/ old_root, com dados lá.
        _write(os.path.join(old_root, ".rpa", "app.db"), "BANCO")
        _write(os.path.join(old_root, "Home", "Recebidos", "marcador.txt"), "ok")
        config.save_config({"data_root": old_root, "theme": "light"})

        # Já existe um arquivo no destino: não pode ser sobrescrito.
        _write(os.path.join(new_root, ".rpa", "app.db"), "MAIS_NOVO")

        result = config.ensure_data_root()

        check("retorna o novo local", config._same_path(result, new_root))
        check("config passou a apontar p/ o novo local",
              config._same_path(config.load_config().get("data_root", ""), new_root))
        check("migrou a árvore Home/Recebidos",
              os.path.isfile(os.path.join(new_root, "Home", "Recebidos", "marcador.txt")))
        with open(os.path.join(new_root, ".rpa", "app.db"), encoding="utf-8") as f:
            kept = f.read()
        check("não sobrescreveu arquivo já existente no destino", kept == "MAIS_NOVO")
        check("preservou outras chaves do config (theme)",
              config.load_config().get("theme") == "light")

    os.environ.pop("RPA_CONFIG_DIR", None)
    os.environ.pop("RPA_DATA_ROOT", None)

    print()
    if _failures:
        print(f"RESULTADO: {len(_failures)} falha(s): {_failures}")
        return 1
    print("RESULTADO: pasta automatica + migracao - OK")
    return 0


if __name__ == "__main__":
    sys.exit(main())
