"""Motor de fórmulas dinâmicas — seguro (sem eval/exec).

Sintaxe inspirada no Excel, em inglês, com ``;`` como separador de argumentos:

    TODAY()
    TODAY()+2
    WORKDAY(TODAY(); -1)
    EOMONTH(TODAY(); 0)
    DATE(2026; 12; 31)
    TEXT(WORKDAY(TODAY(); -1); "yyyy-mm-dd")

A avaliação é feita por um tokenizer + parser recursivo próprios, com uma lista
branca (whitelist) de funções — nunca ``eval``/``exec`` — para evitar execução de
código arbitrário a partir de uma fórmula salva no robô.

Tipos intermediários: date / datetime, int/float e str. O resultado final é
formatado em texto pronto para ser digitado no site (formato padrão dd/mm/yyyy).
"""

from __future__ import annotations

import calendar
from datetime import date, datetime, timedelta


class FormulaError(Exception):
    """Erro de sintaxe ou avaliação de uma fórmula."""


# Referência exibida ao usuário (nome, descrição, exemplo).
FORMULAS = [
    ("TODAY()", "Data de hoje.", "TODAY()"),
    ("NOW()", "Data e hora atuais.", 'TEXT(NOW(); "dd/mm/yyyy hh:nn")'),
    ("DATE(ano; mês; dia)", "Monta uma data específica.", "DATE(2026; 12; 31)"),
    ("WORKDAY(data; dias)", "Soma/subtrai dias ÚTEIS (pula fins de semana e feriados nacionais BR).",
     "WORKDAY(TODAY(); -1)"),
    ("EOMONTH(data; meses)", "Último dia do mês, com deslocamento de meses.", "EOMONTH(TODAY(); 0)"),
    ("EDATE(data; meses)", "Mesma data N meses depois (+) ou antes (-).", "EDATE(TODAY(); -1)"),
    ("YEAR(data)", "Ano (número) de uma data.", "YEAR(TODAY())"),
    ("MONTH(data)", "Mês (número) de uma data.", "MONTH(TODAY())"),
    ("DAY(data)", "Dia (número) de uma data.", "DAY(TODAY())"),
    ("TEXT(valor; formato)", "Formata data/número como texto (dd, mm, yyyy, hh, nn, ss).",
     'TEXT(TODAY(); "yyyy-mm-dd")'),
    ("data + N  /  data - N", "Soma/subtrai N dias de uma data.", "TODAY()+2   |   TODAY()-1"),
]

# Nomes para o autocomplete (com o parêntese de abertura).
FORMULA_NAMES = ["TODAY()", "NOW()", "DATE(", "WORKDAY(", "EOMONTH(", "EDATE(",
                 "YEAR(", "MONTH(", "DAY(", "TEXT("]


# --------------------------------------------------------------------- tokens
_TOKEN_PUNCT = {"(", ")", ";", "+", "-", "*", "/"}


def _tokenize(text: str) -> list[tuple[str, object]]:
    tokens: list[tuple[str, object]] = []
    i, n = 0, len(text)
    while i < n:
        c = text[i]
        if c.isspace():
            i += 1
            continue
        if c in _TOKEN_PUNCT:
            tokens.append((c, c))
            i += 1
            continue
        if c in ('"', "'"):
            quote = c
            i += 1
            start = i
            while i < n and text[i] != quote:
                i += 1
            if i >= n:
                raise FormulaError("String não terminada na fórmula.")
            tokens.append(("STR", text[start:i]))
            i += 1
            continue
        if c.isdigit() or (c == "." and i + 1 < n and text[i + 1].isdigit()):
            start = i
            dot = False
            while i < n and (text[i].isdigit() or text[i] == "."):
                if text[i] == ".":
                    if dot:
                        break
                    dot = True
                i += 1
            num = text[start:i]
            tokens.append(("NUM", float(num) if dot else int(num)))
            continue
        if c.isalpha() or c == "_":
            start = i
            while i < n and (text[i].isalnum() or text[i] == "_"):
                i += 1
            tokens.append(("NAME", text[start:i]))
            continue
        raise FormulaError(f"Caractere inesperado na fórmula: {c!r}")
    tokens.append(("EOF", None))
    return tokens


# --------------------------------------------------------------------- parser
class _Parser:
    def __init__(self, tokens, env):
        self.tokens = tokens
        self.pos = 0
        self.env = env

    def _peek(self):
        return self.tokens[self.pos]

    def _next(self):
        tok = self.tokens[self.pos]
        self.pos += 1
        return tok

    def _expect(self, kind):
        tok = self._next()
        if tok[0] != kind:
            raise FormulaError(f"Esperado {kind!r}, encontrado {tok[1]!r}.")
        return tok

    def parse(self):
        value = self._expr()
        if self._peek()[0] != "EOF":
            raise FormulaError("Tokens em excesso ao final da fórmula.")
        return value

    def _expr(self):
        value = self._term()
        while self._peek()[0] in ("+", "-"):
            op = self._next()[0]
            rhs = self._term()
            value = _binary(op, value, rhs)
        return value

    def _term(self):
        value = self._factor()
        while self._peek()[0] in ("*", "/"):
            op = self._next()[0]
            rhs = self._factor()
            value = _binary(op, value, rhs)
        return value

    def _factor(self):
        kind, val = self._peek()
        if kind == "-":
            self._next()
            return _unary_minus(self._factor())
        if kind == "+":
            self._next()
            return self._factor()
        if kind == "NUM":
            self._next()
            return val
        if kind == "STR":
            self._next()
            return val
        if kind == "(":
            self._next()
            value = self._expr()
            self._expect(")")
            return value
        if kind == "NAME":
            return self._call()
        raise FormulaError(f"Token inesperado: {val!r}")

    def _call(self):
        name = self._next()[1].upper()
        if name not in _FUNCTIONS:
            raise FormulaError(f"Função desconhecida: {name}")
        self._expect("(")
        args = []
        if self._peek()[0] != ")":
            args.append(self._expr())
            while self._peek()[0] == ";":
                self._next()
                args.append(self._expr())
        self._expect(")")
        return _FUNCTIONS[name](self.env, args)


# ----------------------------------------------------------------- operadores
def _as_date(v):
    if isinstance(v, datetime):
        return v.date()
    if isinstance(v, date):
        return v
    return None


def _binary(op, a, b):
    da, db = _as_date(a), _as_date(b)
    if op == "+":
        if da is not None and isinstance(b, (int, float)):
            return da + timedelta(days=int(b))
        if db is not None and isinstance(a, (int, float)):
            return db + timedelta(days=int(a))
        if isinstance(a, (int, float)) and isinstance(b, (int, float)):
            return a + b
        if isinstance(a, str) or isinstance(b, str):
            return f"{_to_text(a)}{_to_text(b)}"
        raise FormulaError("Operação '+' inválida para os tipos informados.")
    if op == "-":
        if da is not None and db is not None:
            return (da - db).days
        if da is not None and isinstance(b, (int, float)):
            return da - timedelta(days=int(b))
        if isinstance(a, (int, float)) and isinstance(b, (int, float)):
            return a - b
        raise FormulaError("Operação '-' inválida para os tipos informados.")
    if op in ("*", "/"):
        if isinstance(a, (int, float)) and isinstance(b, (int, float)):
            if op == "*":
                return a * b
            if b == 0:
                raise FormulaError("Divisão por zero.")
            return a / b
        raise FormulaError(f"Operação '{op}' exige números.")
    raise FormulaError(f"Operador desconhecido: {op}")


def _unary_minus(v):
    if isinstance(v, (int, float)):
        return -v
    raise FormulaError("Negação exige um número.")


# ------------------------------------------------------------------- funções
def _arg_date(env, args, i):
    d = _as_date(args[i])
    if d is None:
        raise FormulaError("Argumento de data esperado.")
    return d


def _fn_today(env, args):
    if args:
        raise FormulaError("TODAY() não aceita argumentos.")
    return env["today"]


def _fn_now(env, args):
    if args:
        raise FormulaError("NOW() não aceita argumentos.")
    return env["now"]


def _fn_date(env, args):
    if len(args) != 3:
        raise FormulaError("DATE(ano; mês; dia) exige 3 argumentos.")
    y, m, d = (int(a) for a in args)
    try:
        return date(y, m, d)
    except ValueError as e:
        raise FormulaError(str(e))


def _fn_workday(env, args):
    if len(args) < 2:
        raise FormulaError("WORKDAY(data; dias) exige ao menos 2 argumentos.")
    start = _arg_date(env, args, 0)
    days = int(args[1])
    cal = env.get("holidays")
    step = 1 if days >= 0 else -1
    remaining = abs(days)
    cur = start
    while remaining > 0:
        cur = cur + timedelta(days=step)
        if cur.weekday() < 5 and (cal is None or cur not in cal):
            remaining -= 1
    return cur


def _fn_eomonth(env, args):
    if len(args) != 2:
        raise FormulaError("EOMONTH(data; meses) exige 2 argumentos.")
    start = _arg_date(env, args, 0)
    months = int(args[1])
    y = start.year + (start.month - 1 + months) // 12
    m = (start.month - 1 + months) % 12 + 1
    return date(y, m, calendar.monthrange(y, m)[1])


def _fn_edate(env, args):
    if len(args) != 2:
        raise FormulaError("EDATE(data; meses) exige 2 argumentos.")
    start = _arg_date(env, args, 0)
    months = int(args[1])
    y = start.year + (start.month - 1 + months) // 12
    m = (start.month - 1 + months) % 12 + 1
    day = min(start.day, calendar.monthrange(y, m)[1])
    return date(y, m, day)


def _fn_year(env, args):
    return _arg_date(env, args, 0).year


def _fn_month(env, args):
    return _arg_date(env, args, 0).month


def _fn_day(env, args):
    return _arg_date(env, args, 0).day


def _fn_text(env, args):
    if len(args) != 2:
        raise FormulaError("TEXT(valor; formato) exige 2 argumentos.")
    return _format_value(args[0], str(args[1]))


_FUNCTIONS = {
    "TODAY": _fn_today,
    "NOW": _fn_now,
    "DATE": _fn_date,
    "WORKDAY": _fn_workday,
    "EOMONTH": _fn_eomonth,
    "EDATE": _fn_edate,
    "YEAR": _fn_year,
    "MONTH": _fn_month,
    "DAY": _fn_day,
    "TEXT": _fn_text,
}


# ---------------------------------------------------------------- formatação
def _fmt_to_strftime(fmt: str) -> str:
    # Ordem importa (tokens maiores primeiro). 'nn' = minutos (evita conflito com mm=mês).
    pairs = [
        ("yyyy", "%Y"), ("yy", "%y"),
        ("mm", "%m"), ("dd", "%d"),
        ("hh", "%H"), ("nn", "%M"), ("ss", "%S"),
    ]
    out, i = [], 0
    low = fmt
    while i < len(low):
        for token, repl in pairs:
            if low[i:i + len(token)] == token:
                out.append(repl)
                i += len(token)
                break
        else:
            out.append(fmt[i])
            i += 1
    return "".join(out)


def _format_value(value, fmt: str) -> str:
    if isinstance(value, (date, datetime)):
        return value.strftime(_fmt_to_strftime(fmt))
    return _to_text(value)


def _to_text(value) -> str:
    if isinstance(value, bool):
        return "VERDADEIRO" if value else "FALSO"
    if isinstance(value, float) and value.is_integer():
        return str(int(value))
    return str(value)


# --------------------------------------------------------------------- API
def evaluate(formula: str, fmt: str = "dd/mm/yyyy", *, today=None,
             holiday_calendar=None) -> str:
    """Avalia uma fórmula e devolve o texto formatado para digitar no site."""
    if formula is None or not str(formula).strip():
        raise FormulaError("Fórmula vazia.")
    now = datetime.now()
    env = {
        "today": today or date.today(),
        "now": now,
        "holidays": holiday_calendar,
    }
    value = _Parser(_tokenize(formula), env).parse()
    return _format_value(value, fmt)


def evaluate_raw(formula: str, *, today=None, holiday_calendar=None):
    """Versão para testes: devolve o valor avaliado (date/número/str), sem formatar."""
    now = datetime.now()
    env = {
        "today": today or date.today(),
        "now": now,
        "holidays": holiday_calendar,
    }
    return _Parser(_tokenize(formula), env).parse()


def format_date(d, fmt: str = "dd/mm/yyyy") -> str:
    """Formata um date/datetime no padrão informado (dd/mm/yyyy etc.)."""
    return d.strftime(_fmt_to_strftime(fmt))


def parse_date(text: str, fmt: str = "dd/mm/yyyy"):
    """Converte um texto em date conforme o formato informado."""
    return datetime.strptime(text.strip(), _fmt_to_strftime(fmt)).date()


def validate(formula: str) -> tuple[bool, str]:
    """Valida a sintaxe avaliando contra uma data fixa. Retorna (ok, mensagem)."""
    try:
        evaluate(formula, today=date(2024, 1, 2))
        return True, "OK"
    except FormulaError as e:
        return False, str(e)
