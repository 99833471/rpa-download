"""Testes do motor de fórmulas, do manifesto e da criptografia de sessão (Fase 2).

Uso:  python tests/formula_test.py
"""

from __future__ import annotations

import os
import sys
import tempfile
from datetime import date

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app import formula  # noqa: E402
from app.robot_manifest import (  # noqa: E402
    FieldConfig, RobotManifest, Selector, SiteLimit, Step,
)
from app.services import crypto  # noqa: E402

_failures = []


def check(label, cond):
    print(f"  [{'OK ' if cond else 'FALHOU'}] {label}")
    if not cond:
        _failures.append(label)


def test_formula():
    print("== Motor de fórmulas ==")
    ref = date(2026, 6, 24)  # quarta-feira

    check("TODAY()", formula.evaluate("TODAY()", today=ref) == "24/06/2026")
    check("TODAY()+2", formula.evaluate("TODAY()+2", today=ref) == "26/06/2026")
    check("TODAY()-1", formula.evaluate("TODAY()-1", today=ref) == "23/06/2026")
    check("DATE(2026;12;31)", formula.evaluate("DATE(2026;12;31)", today=ref) == "31/12/2026")
    check("EOMONTH 0 (jun/26)", formula.evaluate("EOMONTH(TODAY(); 0)", today=ref) == "30/06/2026")
    check("EDATE +1 mês", formula.evaluate("EDATE(TODAY(); 1)", today=ref) == "24/07/2026")
    check("YEAR", formula.evaluate_raw("YEAR(TODAY())", today=ref) == 2026)

    # WORKDAY sem feriados: sexta(26/jun) -> próximo dia útil = segunda 29/jun.
    fri = date(2026, 6, 26)
    check("WORKDAY +1 pula fim de semana",
          formula.evaluate("WORKDAY(TODAY(); 1)", today=fri) == "29/06/2026")
    # WORKDAY -1 a partir de quarta 24/jun = terça 23/jun.
    check("WORKDAY -1", formula.evaluate("WORKDAY(TODAY(); -1)", today=ref) == "23/06/2026")

    # WORKDAY com feriados nacionais BR (lib holidays).
    import holidays
    br = holidays.Brazil()
    # A partir de 24/dez/2025 (qua). 25/dez (qui) é Natal (feriado nacional).
    xmas_eve = date(2025, 12, 24)
    # Sem feriados: +1 dia útil = a própria quinta 25/12.
    check("WORKDAY sem feriados cai no dia 25",
          formula.evaluate("WORKDAY(TODAY(); 1)", today=xmas_eve) == "25/12/2025")
    # Com feriados: pula o Natal e cai em 26/dez (sexta), que é dia útil.
    check("WORKDAY pula feriado nacional (Natal)",
          formula.evaluate("WORKDAY(TODAY(); 1)", today=xmas_eve, holiday_calendar=br) == "26/12/2025")

    check("TEXT formato ISO",
          formula.evaluate('TEXT(TODAY(); "yyyy-mm-dd")', today=ref) == "2026-06-24")

    # Segurança: nada de eval. Função desconhecida e código Python devem falhar.
    ok1, _ = formula.validate("__import__('os')")
    ok2, _ = formula.validate("EVILFUNC()")
    check("rejeita chamada não-whitelisted", not ok1 and not ok2)
    ok3, _ = formula.validate("WORKDAY(TODAY(); -1)")
    check("valida fórmula correta", ok3)


def test_formula_extras():
    print("== Fórmulas: números, texto, lógica, datas extras ==")
    ref = date(2026, 6, 24)  # quarta-feira

    # Combinar / aritmética
    check("aritmética com precedência", formula.evaluate_raw("2+3*4") == 14)
    check("parênteses", formula.evaluate_raw("(2+3)*4") == 20)
    check("divisão decimal", abs(formula.evaluate_raw("10/4") - 2.5) < 1e-9)

    # Números
    check("ROUND", formula.evaluate_raw("ROUND(10/3; 2)") == round(10 / 3, 2))
    check("ABS", formula.evaluate_raw("ABS(-7)") == 7)
    check("MOD", formula.evaluate_raw("MOD(10; 3)") == 1)
    check("MAX", formula.evaluate_raw("MAX(3; 7; 2)") == 7)
    check("SUM", formula.evaluate_raw("SUM(1; 2; 3; 4)") == 10)
    check("POWER", formula.evaluate_raw("POWER(2; 10)") == 1024)
    check("INT", formula.evaluate_raw("INT(9.9)") == 9)

    # Texto
    check("CONCAT", formula.evaluate('CONCAT("REL-"; YEAR(TODAY()))', today=ref) == "REL-2026")
    check("ZEROPAD", formula.evaluate("ZEROPAD(MONTH(TODAY()); 2)", today=ref) == "06")
    check("UPPER", formula.evaluate('UPPER("abc")') == "ABC")
    check("LEFT", formula.evaluate('LEFT("Relatorio"; 3)') == "Rel")
    check("VALUE vírgula", abs(formula.evaluate_raw('VALUE("12,5")') - 12.5) < 1e-9)

    # Datas extras
    check("SOMONTH", formula.evaluate("SOMONTH(TODAY())", today=ref) == "01/06/2026")
    check("WEEKDAY (quarta=3)", formula.evaluate_raw("WEEKDAY(TODAY())", today=ref) == 3)
    check("QUARTER", formula.evaluate_raw("QUARTER(TODAY())", today=ref) == 2)
    check("WORKDAYS jun (1 a 5)",
          formula.evaluate_raw("WORKDAYS(DATE(2026;6;1); DATE(2026;6;5))") == 5)

    # Lógica + comparações
    check("comparação >", formula.evaluate_raw("3 > 2") is True)
    check("IF verdadeiro", formula.evaluate('IF(DAY(TODAY()) > 15; "depois"; "antes")', today=ref) == "depois")
    check("AND", formula.evaluate_raw("AND(1=1; 2>1)") is True)
    check("OR/NOT", formula.evaluate_raw("OR(NOT(1=1); 2>1)") is True)

    # Formato decimal (vírgula BR)
    check("TEXT decimal vírgula", formula.evaluate('TEXT(1234.5; "0,00")') == "1234,50")
    check("TEXT milhar BR", formula.evaluate('TEXT(1234.5; "#.##0,00")') == "1.234,50")

    # Preview
    ok, val = formula.preview("TODAY()")
    check("preview ok", ok and "/" in val)
    bad_ok, _ = formula.preview("EVIL(")
    check("preview erro", not bad_ok)

    # Combinação de datas + número (Today()+1)
    check("combinar Today()+1", formula.evaluate("TODAY()+1", today=ref) == "25/06/2026")


def test_manifest():
    print("== Manifesto robot.json ==")
    m = RobotManifest(
        name="Robô Custos",
        start_url="https://exemplo.com",
        has_login=True,
        session_file="session.bin",
        site_limit=SiteLimit(enabled=True, max_rows=500, strategy="date_partition"),
        steps=[
            Step(action="goto", url="https://exemplo.com"),
            Step(action="fill",
                 selectors=[Selector("css", "#data"), Selector("xpath", "//input[@id='data']")],
                 field=FieldConfig(type="formula", formula="WORKDAY(TODAY(); -1)")),
            Step(action="click", selectors=[Selector("css", "#baixar")]),
            Step(action="download"),
        ],
    )
    with tempfile.TemporaryDirectory() as d:
        path = os.path.join(d, "robot.json")
        m.save(path)
        loaded = RobotManifest.load(path)
    check("round-trip preserva nome", loaded.name == "Robô Custos")
    check("round-trip preserva limite", loaded.site_limit.max_rows == 500)
    check("round-trip preserva nº de passos", len(loaded.steps) == 4)
    check("round-trip preserva 2 seletores no fill", len(loaded.steps[1].selectors) == 2)
    check("round-trip preserva tipo de campo fórmula",
          loaded.steps[1].field.type == "formula")
    check("created_at preenchido ao salvar", bool(loaded.created_at))


def test_crypto():
    print("== Criptografia de sessão (DPAPI) ==")
    secret = b'{"cookies": [{"name": "sid", "value": "abc123"}]}'
    blob = crypto.encrypt_bytes(secret)
    check("texto cifrado difere do original", blob != secret)
    check("descriptografa de volta ao original", crypto.decrypt_bytes(blob) == secret)
    with tempfile.TemporaryDirectory() as d:
        p = os.path.join(d, "sub", "session.bin")
        crypto.save_encrypted(p, secret)
        check("arquivo salvo existe", os.path.isfile(p))
        check("arquivo lido confere", crypto.load_encrypted(p) == secret)
    check("DPAPI ativo no Windows", crypto.is_protected() is True)


def main():
    test_formula()
    test_formula_extras()
    test_manifest()
    test_crypto()
    print()
    if _failures:
        print(f"RESULTADO: {len(_failures)} falha(s): {_failures}")
        return 1
    print("RESULTADO: formulas + manifesto + crypto - OK")
    return 0


if __name__ == "__main__":
    sys.exit(main())
