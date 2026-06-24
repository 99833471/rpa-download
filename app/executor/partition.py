"""Particionamento recursivo de intervalos de data (lógica adaptativa de limites).

Quando o site limita a quantidade de linhas por download, dividimos o intervalo
de datas ao meio recursivamente até que cada subintervalo "libere" o download.

Esta lógica é pura (não depende do Playwright) para ser testável: recebe um
``test_fn(inicio, fim) -> bool`` que diz se aquele intervalo foi liberado.
"""

from __future__ import annotations

from datetime import date, timedelta


def partition_plan(start: date, end: date, test_fn):
    """Bisecção recursiva. Retorna (liberados, falhos) como listas de (ini, fim).

    - Tenta o intervalo inteiro; se liberar, ótimo.
    - Se não, divide ao meio e tenta cada metade.
    - Caso base: um único dia que ainda não libera entra em ``falhos``.

    A ordem dos ``liberados`` cobre o intervalo da esquerda para a direita, sem
    lacunas nem sobreposição.
    """
    if start > end:
        start, end = end, start
    succeeded: list[tuple[date, date]] = []
    failed: list[tuple[date, date]] = []

    def rec(a: date, b: date):
        if test_fn(a, b):
            succeeded.append((a, b))
            return
        if a >= b:
            failed.append((a, b))
            return
        mid = a + (b - a) // 2
        rec(a, mid)
        rec(mid + timedelta(days=1), b)

    rec(start, end)
    return succeeded, failed
