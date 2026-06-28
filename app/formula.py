"""Motor de fórmulas dinâmicas — seguro (sem eval/exec).

Sintaxe inspirada no Excel, em inglês, com ``;`` como separador de argumentos:

    TODAY()
    TODAY()+2
    WORKDAY(TODAY(); -1)
    EOMONTH(TODAY(); 0)
    DATE(2026; 12; 31)
    TEXT(WORKDAY(TODAY(); -1); "yyyy-mm-dd")
    ROUND(10/3; 2)
    ZEROPAD(MONTH(TODAY()); 2)
    IF(DAY(TODAY()) > 15; "depois"; "antes")

A avaliação é feita por um tokenizer + parser recursivo próprios, com uma lista
branca (whitelist) de funções — nunca ``eval``/``exec`` — para evitar execução de
código arbitrário a partir de uma fórmula salva no robô.

Operadores: + - * /  (aritmética e dias em datas), comparações = <> < > <= >=,
parênteses e precedência. Tipos: date/datetime, int/float, bool e str. O resultado
final é formatado em texto pronto para digitar no site (padrão dd/mm/yyyy).
"""

from __future__ import annotations

import calendar
import math
from datetime import date, datetime, timedelta


class FormulaError(Exception):
    """Erro de sintaxe ou avaliação de uma fórmula."""


# Referência exibida ao usuário (nome, descrição, exemplo), agrupada por categoria.
FORMULAS = [
    # --- Datas ---
    ("TODAY()", "Data de hoje.", "TODAY()"),
    ("NOW()", "Data e hora atuais.", 'TEXT(NOW(); "dd/mm/yyyy hh:nn")'),
    ("DATE(ano; mês; dia)", "Monta uma data específica.", "DATE(2026; 12; 31)"),
    ("WORKDAY(data; dias)", "Soma/subtrai dias ÚTEIS (pula fins de semana e feriados nacionais BR).",
     "WORKDAY(TODAY(); -1)"),
    ("WORKDAYS(data1; data2)", "Quantidade de dias úteis entre duas datas (feriados BR).",
     "WORKDAYS(SOMONTH(TODAY()); TODAY())"),
    ("EOMONTH(data; meses)", "Último dia do mês, com deslocamento de meses.", "EOMONTH(TODAY(); 0)"),
    ("SOMONTH(data; meses)", "Primeiro dia do mês, com deslocamento de meses.", "SOMONTH(TODAY(); 0)"),
    ("EDATE(data; meses)", "Mesma data N meses depois (+) ou antes (-).", "EDATE(TODAY(); -1)"),
    ("YEAR(data)", "Ano (número) de uma data.", "YEAR(TODAY())"),
    ("MONTH(data)", "Mês (número) de uma data.", "MONTH(TODAY())"),
    ("DAY(data)", "Dia (número) de uma data.", "DAY(TODAY())"),
    ("WEEKDAY(data)", "Dia da semana (1=segunda … 7=domingo).", "WEEKDAY(TODAY())"),
    ("WEEKNUM(data)", "Número da semana no ano (ISO).", "WEEKNUM(TODAY())"),
    ("QUARTER(data)", "Trimestre (1 a 4).", "QUARTER(TODAY())"),
    ("HOUR(data) / MINUTE / SECOND", "Hora/minuto/segundo de uma data-hora.", "HOUR(NOW())"),
    ("TEXT(valor; formato)", "Formata data/número como texto (dd, mm, yyyy, hh, nn, ss; ou 0,00).",
     'TEXT(TODAY(); "yyyy-mm-dd")'),
    ("data + N  /  data - N", "Soma/subtrai N dias de uma data.", "TODAY()+2   |   TODAY()-1"),
    ("data1 - data2", "Diferença em dias entre duas datas.", "TODAY() - DATE(2026;1;1)"),
    # --- Números ---
    ("ROUND(num; casas)", "Arredonda para N casas decimais.", "ROUND(10/3; 2)"),
    ("ROUNDUP / ROUNDDOWN(num; casas)", "Arredonda para cima / para baixo.", "ROUNDUP(1.234; 1)"),
    ("INT(num) / TRUNC(num)", "Parte inteira (INT arredonda p/ baixo; TRUNC corta).", "INT(9.9)"),
    ("ABS(num)", "Valor absoluto.", "ABS(-5)"),
    ("MOD(a; b)", "Resto da divisão.", "MOD(10; 3)"),
    ("POWER(a; b) / SQRT(num)", "Potência / raiz quadrada.", "POWER(2; 10)"),
    ("CEILING(num) / FLOOR(num)", "Arredonda p/ o inteiro acima / abaixo.", "CEILING(2.1)"),
    ("MIN(…) / MAX(…)", "Menor / maior valor.", "MAX(3; 7; 2)"),
    ("SUM(…) / AVERAGE(…)", "Soma / média dos valores.", "SUM(1; 2; 3)"),
    # --- Texto ---
    ("CONCAT(…)", "Junta vários textos.", 'CONCAT("REL-"; YEAR(TODAY()))'),
    ("UPPER / LOWER / TRIM(texto)", "Maiúsculas / minúsculas / remove espaços nas pontas.", 'UPPER("abc")'),
    ("LEFT / RIGHT(texto; n)", "N caracteres da esquerda / direita.", 'LEFT("Relatorio"; 3)'),
    ("MID(texto; início; n)", "N caracteres a partir da posição (1 = primeiro).", 'MID("ABCDE"; 2; 3)'),
    ("LEN(texto)", "Quantidade de caracteres.", 'LEN("abc")'),
    ("ZEROPAD(valor; n)", "Preenche com zeros à esquerda (ex.: 6 → 06).", "ZEROPAD(MONTH(TODAY()); 2)"),
    ("SUBSTITUTE(texto; de; para)", "Substitui um trecho por outro.", 'SUBSTITUTE("a-b-c"; "-"; "/")'),
    ("VALUE(texto)", "Converte texto em número.", 'VALUE("12,5")'),
    # --- Lógica ---
    ("IF(condição; a; b)", "Retorna a se a condição for verdadeira, senão b.",
     'IF(DAY(TODAY()) > 15; "2a"; "1a")'),
    ("AND(…) / OR(…) / NOT(x)", "Combinações lógicas.", "AND(1=1; 2>1)"),
    ("comparações", "= (igual), <> (diferente), <, >, <=, >=.", "TODAY() > DATE(2026;1;1)"),
]

# Nomes para o autocomplete (com o parêntese de abertura).
FORMULA_NAMES = [
    "TODAY()", "NOW()", "DATE(", "WORKDAY(", "WORKDAYS(", "EOMONTH(", "SOMONTH(",
    "EDATE(", "YEAR(", "MONTH(", "DAY(", "WEEKDAY(", "WEEKNUM(", "QUARTER(",
    "HOUR(", "MINUTE(", "SECOND(", "TEXT(",
    "ROUND(", "ROUNDUP(", "ROUNDDOWN(", "INT(", "TRUNC(", "ABS(", "MOD(",
    "POWER(", "SQRT(", "CEILING(", "FLOOR(", "MIN(", "MAX(", "SUM(", "AVERAGE(",
    "CONCAT(", "UPPER(", "LOWER(", "TRIM(", "LEFT(", "RIGHT(", "MID(", "LEN(",
    "ZEROPAD(", "SUBSTITUTE(", "VALUE(",
    "IF(", "AND(", "OR(", "NOT(", "TRUE()", "FALSE()",
]


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
        if c in "<>=":  # operadores de comparação (incl. <=, >=, <>)
            two = text[i:i + 2]
            if two in ("<=", ">=", "<>"):
                tokens.append((two, two))
                i += 2
            else:
                tokens.append((c, c))
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
_COMPARATORS = ("=", "<>", "<", ">", "<=", ">=")


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
        return self._comparison()

    def _comparison(self):
        value = self._addsub()
        while self._peek()[0] in _COMPARATORS:
            op = self._next()[0]
            rhs = self._addsub()
            value = _compare(op, value, rhs)
        return value

    def _addsub(self):
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
        if da is not None and isinstance(b, (int, float)) and not isinstance(b, bool):
            return da + timedelta(days=int(b))
        if db is not None and isinstance(a, (int, float)) and not isinstance(a, bool):
            return db + timedelta(days=int(a))
        if _is_num(a) and _is_num(b):
            return _num(a) + _num(b)
        if isinstance(a, str) or isinstance(b, str):
            return f"{_to_text(a)}{_to_text(b)}"
        raise FormulaError("Operação '+' inválida para os tipos informados.")
    if op == "-":
        if da is not None and db is not None:
            return (da - db).days
        if da is not None and isinstance(b, (int, float)) and not isinstance(b, bool):
            return da - timedelta(days=int(b))
        if _is_num(a) and _is_num(b):
            return _num(a) - _num(b)
        raise FormulaError("Operação '-' inválida para os tipos informados.")
    if op in ("*", "/"):
        if _is_num(a) and _is_num(b):
            x, y = _num(a), _num(b)
            if op == "*":
                return x * y
            if y == 0:
                raise FormulaError("Divisão por zero.")
            return x / y
        raise FormulaError(f"Operação '{op}' exige números.")
    raise FormulaError(f"Operador desconhecido: {op}")


def _unary_minus(v):
    if _is_num(v):
        return -_num(v)
    raise FormulaError("Negação exige um número.")


def _truthy(v) -> bool:
    if isinstance(v, bool):
        return v
    if isinstance(v, (int, float)):
        return v != 0
    if isinstance(v, str):
        return v.strip() != ""
    return v is not None


def _compare(op, a, b):
    da, db = _as_date(a), _as_date(b)
    x = da if da is not None else a
    y = db if db is not None else b
    try:
        if op == "=":
            return x == y
        if op == "<>":
            return x != y
        if op == "<":
            return x < y
        if op == ">":
            return x > y
        if op == "<=":
            return x <= y
        if op == ">=":
            return x >= y
    except TypeError:
        raise FormulaError("Comparação entre tipos incompatíveis.")
    raise FormulaError(f"Operador de comparação desconhecido: {op}")


# ------------------------------------------------------------------- funções
def _is_num(v) -> bool:
    return isinstance(v, (int, float)) and not isinstance(v, bool)


def _num(v) -> float | int:
    if isinstance(v, bool):
        return 1 if v else 0
    if isinstance(v, (int, float)):
        return v
    if isinstance(v, str):
        s = v.strip().replace(",", ".")
        try:
            return float(s) if "." in s else int(s)
        except ValueError:
            raise FormulaError(f"Valor numérico inválido: {v!r}")
    raise FormulaError("Esperado um número.")


def _arg_date(env, args, i):
    d = _as_date(args[i])
    if d is None:
        raise FormulaError("Argumento de data esperado.")
    return d


def _arg_dt(env, args, i):
    v = args[i]
    if isinstance(v, datetime):
        return v
    if isinstance(v, date):
        return datetime(v.year, v.month, v.day)
    raise FormulaError("Argumento de data/hora esperado.")


def _flat_nums(args):
    return [_num(a) for a in args]


# ---- datas ----
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
    y, m, d = (int(_num(a)) for a in args)
    try:
        return date(y, m, d)
    except ValueError as e:
        raise FormulaError(str(e))


def _fn_workday(env, args):
    if len(args) < 2:
        raise FormulaError("WORKDAY(data; dias) exige ao menos 2 argumentos.")
    start = _arg_date(env, args, 0)
    days = int(_num(args[1]))
    cal = env.get("holidays")
    step = 1 if days >= 0 else -1
    remaining = abs(days)
    cur = start
    while remaining > 0:
        cur = cur + timedelta(days=step)
        if cur.weekday() < 5 and (cal is None or cur not in cal):
            remaining -= 1
    return cur


def _fn_workdays(env, args):
    if len(args) != 2:
        raise FormulaError("WORKDAYS(data1; data2) exige 2 argumentos.")
    a = _arg_date(env, args, 0)
    b = _arg_date(env, args, 1)
    cal = env.get("holidays")
    lo, hi = (a, b) if a <= b else (b, a)
    count = 0
    cur = lo
    while cur <= hi:
        if cur.weekday() < 5 and (cal is None or cur not in cal):
            count += 1
        cur += timedelta(days=1)
    return count


def _shift_month(start, months):
    y = start.year + (start.month - 1 + months) // 12
    m = (start.month - 1 + months) % 12 + 1
    return y, m


def _fn_eomonth(env, args):
    if not (1 <= len(args) <= 2):
        raise FormulaError("EOMONTH(data; meses) exige 1 ou 2 argumentos.")
    start = _arg_date(env, args, 0)
    months = int(_num(args[1])) if len(args) > 1 else 0
    y, m = _shift_month(start, months)
    return date(y, m, calendar.monthrange(y, m)[1])


def _fn_somonth(env, args):
    if not (1 <= len(args) <= 2):
        raise FormulaError("SOMONTH(data; meses) exige 1 ou 2 argumentos.")
    start = _arg_date(env, args, 0)
    months = int(_num(args[1])) if len(args) > 1 else 0
    y, m = _shift_month(start, months)
    return date(y, m, 1)


def _fn_edate(env, args):
    if len(args) != 2:
        raise FormulaError("EDATE(data; meses) exige 2 argumentos.")
    start = _arg_date(env, args, 0)
    months = int(_num(args[1]))
    y, m = _shift_month(start, months)
    day = min(start.day, calendar.monthrange(y, m)[1])
    return date(y, m, day)


def _fn_year(env, args):
    return _arg_date(env, args, 0).year


def _fn_month(env, args):
    return _arg_date(env, args, 0).month


def _fn_day(env, args):
    return _arg_date(env, args, 0).day


def _fn_weekday(env, args):
    return _arg_date(env, args, 0).isoweekday()  # 1=segunda .. 7=domingo


def _fn_weeknum(env, args):
    return _arg_date(env, args, 0).isocalendar()[1]


def _fn_quarter(env, args):
    return (_arg_date(env, args, 0).month - 1) // 3 + 1


def _fn_hour(env, args):
    return _arg_dt(env, args, 0).hour


def _fn_minute(env, args):
    return _arg_dt(env, args, 0).minute


def _fn_second(env, args):
    return _arg_dt(env, args, 0).second


# ---- números ----
def _fn_round(env, args):
    if not (1 <= len(args) <= 2):
        raise FormulaError("ROUND(num; casas) exige 1 ou 2 argumentos.")
    n = _num(args[0])
    d = int(_num(args[1])) if len(args) > 1 else 0
    return round(n, d)


def _fn_roundup(env, args):
    n = _num(args[0])
    d = int(_num(args[1])) if len(args) > 1 else 0
    f = 10 ** d
    return math.ceil(abs(n) * f) / f * (1 if n >= 0 else -1)


def _fn_rounddown(env, args):
    n = _num(args[0])
    d = int(_num(args[1])) if len(args) > 1 else 0
    f = 10 ** d
    return math.floor(abs(n) * f) / f * (1 if n >= 0 else -1)


def _fn_int(env, args):
    return math.floor(_num(args[0]))


def _fn_trunc(env, args):
    return math.trunc(_num(args[0]))


def _fn_abs(env, args):
    return abs(_num(args[0]))


def _fn_mod(env, args):
    if len(args) != 2:
        raise FormulaError("MOD(a; b) exige 2 argumentos.")
    a, b = _num(args[0]), _num(args[1])
    if b == 0:
        raise FormulaError("MOD: divisão por zero.")
    return a - b * math.floor(a / b)


def _fn_power(env, args):
    if len(args) != 2:
        raise FormulaError("POWER(a; b) exige 2 argumentos.")
    return _num(args[0]) ** _num(args[1])


def _fn_sqrt(env, args):
    n = _num(args[0])
    if n < 0:
        raise FormulaError("SQRT exige um número não negativo.")
    return math.sqrt(n)


def _fn_ceiling(env, args):
    return math.ceil(_num(args[0]))


def _fn_floor(env, args):
    return math.floor(_num(args[0]))


def _fn_min(env, args):
    if not args:
        raise FormulaError("MIN exige ao menos 1 valor.")
    return min(_flat_nums(args))


def _fn_max(env, args):
    if not args:
        raise FormulaError("MAX exige ao menos 1 valor.")
    return max(_flat_nums(args))


def _fn_sum(env, args):
    return sum(_flat_nums(args))


def _fn_average(env, args):
    nums = _flat_nums(args)
    if not nums:
        raise FormulaError("AVERAGE exige ao menos 1 valor.")
    return sum(nums) / len(nums)


# ---- texto ----
def _fn_concat(env, args):
    return "".join(_to_text(a) for a in args)


def _fn_upper(env, args):
    return _to_text(args[0]).upper()


def _fn_lower(env, args):
    return _to_text(args[0]).lower()


def _fn_trim(env, args):
    return _to_text(args[0]).strip()


def _fn_left(env, args):
    if len(args) != 2:
        raise FormulaError("LEFT(texto; n) exige 2 argumentos.")
    return _to_text(args[0])[:max(0, int(_num(args[1])))]


def _fn_right(env, args):
    if len(args) != 2:
        raise FormulaError("RIGHT(texto; n) exige 2 argumentos.")
    n = max(0, int(_num(args[1])))
    return _to_text(args[0])[-n:] if n else ""


def _fn_mid(env, args):
    if len(args) != 3:
        raise FormulaError("MID(texto; início; n) exige 3 argumentos.")
    s = _to_text(args[0])
    start = max(1, int(_num(args[1])))
    n = max(0, int(_num(args[2])))
    return s[start - 1:start - 1 + n]


def _fn_len(env, args):
    return len(_to_text(args[0]))


def _fn_zeropad(env, args):
    if len(args) != 2:
        raise FormulaError("ZEROPAD(valor; n) exige 2 argumentos.")
    return _to_text(args[0]).zfill(int(_num(args[1])))


def _fn_substitute(env, args):
    if len(args) != 3:
        raise FormulaError("SUBSTITUTE(texto; de; para) exige 3 argumentos.")
    return _to_text(args[0]).replace(_to_text(args[1]), _to_text(args[2]))


def _fn_value(env, args):
    return _num(args[0])


# ---- lógica ----
def _fn_if(env, args):
    if len(args) != 3:
        raise FormulaError("IF(condição; a; b) exige 3 argumentos.")
    return args[1] if _truthy(args[0]) else args[2]


def _fn_and(env, args):
    return all(_truthy(a) for a in args)


def _fn_or(env, args):
    return any(_truthy(a) for a in args)


def _fn_not(env, args):
    if len(args) != 1:
        raise FormulaError("NOT(x) exige 1 argumento.")
    return not _truthy(args[0])


def _fn_true(env, args):
    return True


def _fn_false(env, args):
    return False


def _fn_text(env, args):
    if len(args) != 2:
        raise FormulaError("TEXT(valor; formato) exige 2 argumentos.")
    return _format_value(args[0], str(args[1]))


_FUNCTIONS = {
    # datas
    "TODAY": _fn_today, "NOW": _fn_now, "DATE": _fn_date,
    "WORKDAY": _fn_workday, "WORKDAYS": _fn_workdays,
    "EOMONTH": _fn_eomonth, "SOMONTH": _fn_somonth, "EDATE": _fn_edate,
    "YEAR": _fn_year, "MONTH": _fn_month, "DAY": _fn_day,
    "WEEKDAY": _fn_weekday, "WEEKNUM": _fn_weeknum, "QUARTER": _fn_quarter,
    "HOUR": _fn_hour, "MINUTE": _fn_minute, "SECOND": _fn_second,
    "TEXT": _fn_text,
    # números
    "ROUND": _fn_round, "ROUNDUP": _fn_roundup, "ROUNDDOWN": _fn_rounddown,
    "INT": _fn_int, "TRUNC": _fn_trunc, "ABS": _fn_abs, "MOD": _fn_mod,
    "POWER": _fn_power, "SQRT": _fn_sqrt, "CEILING": _fn_ceiling, "FLOOR": _fn_floor,
    "MIN": _fn_min, "MAX": _fn_max, "SUM": _fn_sum, "AVERAGE": _fn_average,
    # texto
    "CONCAT": _fn_concat, "UPPER": _fn_upper, "LOWER": _fn_lower, "TRIM": _fn_trim,
    "LEFT": _fn_left, "RIGHT": _fn_right, "MID": _fn_mid, "LEN": _fn_len,
    "ZEROPAD": _fn_zeropad, "SUBSTITUTE": _fn_substitute, "VALUE": _fn_value,
    # lógica
    "IF": _fn_if, "AND": _fn_and, "OR": _fn_or, "NOT": _fn_not,
    "TRUE": _fn_true, "FALSE": _fn_false,
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


def _is_numeric_pattern(fmt: str) -> bool:
    return any(ch in fmt for ch in "0#") and not any(ch.isalpha() for ch in fmt)


def _format_number(value, pattern: str) -> str:
    """Formata um número conforme um padrão tipo 0.00 / 0,00 / #.##0,00.

    O ÚLTIMO separador ('.' ou ',') do padrão é o decimal; o outro, se houver, é o
    separador de milhar.
    """
    last_dot = pattern.rfind(".")
    last_comma = pattern.rfind(",")
    if last_dot == -1 and last_comma == -1:
        dec, dsep, tsep = 0, "", ""
    elif last_dot >= last_comma:
        dsep, tsep = ".", ("," if last_comma != -1 else "")
        dec = sum(1 for ch in pattern[last_dot + 1:] if ch in "0#")
    else:
        dsep, tsep = ",", ("." if last_dot != -1 else "")
        dec = sum(1 for ch in pattern[last_comma + 1:] if ch in "0#")
    s = f"{_num(value):,.{dec}f}"  # ',' milhar e '.' decimal (padrão Python)
    s = s.replace(",", "\x00").replace(".", dsep)
    s = s.replace("\x00", tsep) if tsep else s.replace("\x00", "")
    return s


def _format_value(value, fmt: str) -> str:
    if isinstance(value, (date, datetime)):
        return value.strftime(_fmt_to_strftime(fmt))
    if _is_num(value) and _is_numeric_pattern(fmt):
        return _format_number(value, fmt)
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
    """Versão para testes: devolve o valor avaliado (date/número/bool/str), sem formatar."""
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


def preview(formula: str, fmt: str = "dd/mm/yyyy") -> tuple[bool, str]:
    """Avalia a fórmula com a data de hoje (e feriados BR) para mostrar o resultado
    ao vivo na interface. Retorna (ok, resultado_ou_erro)."""
    if not str(formula or "").strip():
        return False, ""
    try:
        import holidays
        cal = holidays.Brazil()
    except Exception:
        cal = None
    try:
        return True, evaluate(formula, fmt=fmt, holiday_calendar=cal)
    except FormulaError as e:
        return False, str(e)
    except Exception as e:  # noqa: BLE001
        return False, str(e)
