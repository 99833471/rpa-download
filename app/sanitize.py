"""Higienização de nomes para o sistema de arquivos do Windows.

A estrutura visual do programa é espelhada em pastas físicas, então todo nome de
Tela/Bloco/Robô precisa ser convertido em um nome de pasta válido no Windows.
"""

from __future__ import annotations

import re

# Caracteres proibidos pelo Windows em nomes de arquivo/pasta + caracteres de controle.
_FORBIDDEN_RE = re.compile(r'[<>:"/\\|?*\x00-\x1f]')

# Nomes reservados do Windows (case-insensitive).
_RESERVED = {
    "CON", "PRN", "AUX", "NUL",
    *(f"COM{i}" for i in range(1, 10)),
    *(f"LPT{i}" for i in range(1, 10)),
}

MAX_LEN = 120


def sanitize_name(name: str, fallback: str = "SemNome", max_len: int = MAX_LEN) -> str:
    """Converte um texto livre em um nome de pasta seguro para o Windows.

    - Remove caracteres proibidos: < > : " / \\ | ? * e de controle.
    - Remove espaços/pontos no início e fim (o Windows não permite no fim).
    - Colapsa espaços múltiplos.
    - Evita nomes reservados (CON, PRN, COM1, ...).
    - Garante um fallback quando o resultado fica vazio.
    """
    if not name:
        return fallback

    cleaned = _FORBIDDEN_RE.sub("", name)
    cleaned = re.sub(r"\s+", " ", cleaned).strip()
    # Windows não aceita ponto/espaço no final do nome.
    cleaned = cleaned.strip(" .")

    if not cleaned:
        return fallback

    if cleaned.upper() in _RESERVED:
        cleaned = f"_{cleaned}"

    return cleaned[:max_len].strip(" .") or fallback


def make_unique(desired: str, taken) -> str:
    """Garante que ``desired`` seja único dentro de ``taken`` (case-insensitive).

    Em caso de colisão, acrescenta " (2)", " (3)"... como o Explorer do Windows.
    ``taken`` é qualquer iterável de nomes já existentes entre os irmãos.
    """
    taken_lower = {t.lower() for t in taken}
    if desired.lower() not in taken_lower:
        return desired
    i = 2
    while f"{desired} ({i})".lower() in taken_lower:
        i += 1
    return f"{desired} ({i})"
