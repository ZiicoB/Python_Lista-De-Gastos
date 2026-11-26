"""Camada de persistência, autenticação e validação do sistema de gastos."""

from __future__ import annotations

import base64
import calendar
import csv
import hashlib
import hmac
import os
import re
import secrets
from dataclasses import dataclass
from datetime import date, datetime
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent
USERS_FILENAME = "Usuarios.csv"
EXPENSES_DIRNAME = "Arquivos"
SALARIES_FILENAME = "salarios.csv"
SESSION_FILENAME = "sessao.csv"

PBKDF2_PREFIX = "pbkdf2_sha256"
PBKDF2_ITERATIONS = 100_000
USERNAME_PATTERN = re.compile(r"^[A-Za-z0-9_-]{2,32}$")
MONTH_NAMES_PT: dict[int, str] = {
    1: "Jan",
    2: "Fev",
    3: "Mar",
    4: "Abr",
    5: "Mai",
    6: "Jun",
    7: "Jul",
    8: "Ago",
    9: "Set",
    10: "Out",
    11: "Nov",
    12: "Dez",
}
MONTH_FULL_NAMES_PT: dict[int, str] = {
    1: "Janeiro",
    2: "Fevereiro",
    3: "Março",
    4: "Abril",
    5: "Maio",
    6: "Junho",
    7: "Julho",
    8: "Agosto",
    9: "Setembro",
    10: "Outubro",
    11: "Novembro",
    12: "Dezembro",
}


class ValidationError(ValueError):
    """Erro lançado quando uma entrada do usuário não atende às regras."""


@dataclass(frozen=True)
class Expense:
    """Representa um registro de despesa de um usuário."""

    username: str
    category: str
    amount: Decimal
    expense_date: str


def get_users_file(base_dir: Path = BASE_DIR) -> Path:
    """Retorna o caminho do arquivo de usuários garantindo sua existência."""
    base_dir.mkdir(parents=True, exist_ok=True)
    users_file = base_dir / USERS_FILENAME
    if not users_file.exists():
        users_file.write_text("", encoding="utf-8")
    return users_file


def get_expenses_dir(base_dir: Path = BASE_DIR) -> Path:
    """Retorna o diretório de arquivos de despesas garantindo sua existência."""
    expenses_dir = base_dir / EXPENSES_DIRNAME
    expenses_dir.mkdir(parents=True, exist_ok=True)
    return expenses_dir


def validate_username(username: str) -> str:
    """Valida o nome de usuário contra caracteres inválidos e path traversal."""
    cleaned = username.strip()
    if not USERNAME_PATTERN.fullmatch(cleaned):
        raise ValidationError(
            "Usuário inválido. Use de 2 a 32 caracteres (letras, números, '_' ou '-')."
        )
    return cleaned


def validate_password(password: str) -> str:
    """Valida requisitos mínimos da senha."""
    if not password or len(password) < 4:
        raise ValidationError("A senha deve ter pelo menos 4 caracteres.")
    if any(ch in password for ch in ("\r", "\n", "\x00")):
        raise ValidationError("A senha contém caracteres inválidos.")
    return password


def validate_category(category: str) -> str:
    """Valida e normaliza o nome da categoria da despesa."""
    cleaned = category.strip()
    if not cleaned:
        raise ValidationError("A categoria não pode ficar vazia.")
    if any(ch in cleaned for ch in ("\r", "\n", "\x00")):
        raise ValidationError("A categoria contém caracteres inválidos.")
    return cleaned


def format_brl(amount: Decimal) -> str:
    """Formata um Decimal no padrão monetário brasileiro (ex: R$ 1.234,56)."""
    quantized = amount.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
    formatted = f"{quantized:,.2f}"
    # Troca separadores US (1,234.56) para BR (1.234,56)
    br_number = formatted.replace(",", "_").replace(".", ",").replace("_", ".")
    return f"R$ {br_number}"


def format_currency_from_digits(raw: str, *, max_digits: int = 12) -> str:
    """Converte dígitos digitados em formato de moeda real (25 -> R$ 0,25)."""
    digits = re.sub(r"\D", "", raw)[:max_digits]
    if not digits:
        return "R$ 0,00"
    cents = int(digits)
    return format_brl(Decimal(cents) / Decimal("100"))


def parse_amount(raw_amount: str) -> Decimal:
    """Converte uma string monetária (ex: 'R$ 1.234,56', '10,50', '10.50') em Decimal positivo."""
    cleaned = raw_amount.strip()
    cleaned = re.sub(r"(?i)^r\$\s*", "", cleaned).strip()
    if not cleaned:
        raise ValidationError("O valor não pode ficar vazio.")

    if "," in cleaned and "." in cleaned:
        cleaned = cleaned.replace(".", "").replace(",", ".")
    elif "," in cleaned:
        cleaned = cleaned.replace(",", ".")

    try:
        amount = Decimal(cleaned)
    except InvalidOperation as exc:
        raise ValidationError("Valor inválido. Digite um número positivo (ex: 45.90).") from exc

    if not amount.is_finite() or amount <= Decimal("0"):
        raise ValidationError("O valor deve ser maior que zero.")

    return amount.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)


def parse_salary(raw_salary: str) -> Decimal:
    """Converte uma string monetária em Decimal não negativo para o salário mensal."""
    cleaned = raw_salary.strip()
    cleaned = re.sub(r"(?i)^r\$\s*", "", cleaned).strip()
    if not cleaned:
        return Decimal("0.00")

    if "," in cleaned and "." in cleaned:
        cleaned = cleaned.replace(".", "").replace(",", ".")
    elif "," in cleaned:
        cleaned = cleaned.replace(",", ".")

    try:
        amount = Decimal(cleaned)
    except InvalidOperation as exc:
        raise ValidationError("Salário inválido.") from exc

    if not amount.is_finite() or amount < Decimal("0"):
        raise ValidationError("O salário não pode ser negativo.")

    return amount.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)


def default_date_for_month(month_key: str, today: date | None = None) -> str:
    """Retorna uma data válida 'DD/MM/AAAA' dentro do mês 'MM/AAAA' informado."""
    ref = today or date.today()
    try:
        month_str, year_str = month_key.split("/")
        month_num = int(month_str)
        year_num = int(year_str)
        last_day = calendar.monthrange(year_num, month_num)[1]
        day_num = min(ref.day, last_day)
        return date(year_num, month_num, day_num).strftime("%d/%m/%Y")
    except (ValueError, IndexError):
        return ref.strftime("%d/%m/%Y")


def parse_date(
    raw_date: str,
    today: date | None = None,
    *,
    default_month_key: str | None = None,
) -> str:
    """Valida data nos formatos DD/MM, DD/MM/AA, DD/MM/AAAA, DDMMAAAA ou dia (com mês padrão)."""
    cleaned = raw_date.strip()
    ref_today = today or date.today()

    if default_month_key:
        try:
            def_m_str, def_y_str = default_month_key.split("/")
            ref_month = int(def_m_str)
            ref_year = int(def_y_str)
        except ValueError:
            ref_month = ref_today.month
            ref_year = ref_today.year
    else:
        ref_month = ref_today.month
        ref_year = ref_today.year

    if not cleaned:
        if default_month_key:
            return default_date_for_month(default_month_key, ref_today)
        raise ValidationError("A data não pode ficar vazia.")

    # Aceita apenas o dia (1-31) quando há um mês selecionado no painel.
    if default_month_key and re.fullmatch(r"\d{1,2}", cleaned):
        try:
            parsed = date(ref_year, ref_month, int(cleaned))
            return parsed.strftime("%d/%m/%Y")
        except ValueError as exc:
            raise ValidationError("Dia inválido para o mês selecionado.") from exc

    # Aceita DDMMAAAA sem barras (8 dígitos).
    if re.fullmatch(r"\d{8}", cleaned):
        cleaned = f"{cleaned[:2]}/{cleaned[2:4]}/{cleaned[4:]}"

    try:
        if cleaned.count("/") == 1:
            parsed = datetime.strptime(f"{cleaned}/{ref_year}", "%d/%m/%Y").date()
        elif cleaned.count("/") == 2 and len(cleaned.rsplit("/", 1)[-1]) == 2:
            parsed = datetime.strptime(cleaned, "%d/%m/%y").date()
        else:
            parsed = datetime.strptime(cleaned, "%d/%m/%Y").date()
        return parsed.strftime("%d/%m/%Y")
    except ValueError as exc:
        raise ValidationError("Data inválida. Use o formato DD/MM ou DD/MM/AAAA.") from exc


def hash_password(password: str, salt: str | None = None) -> str:
    """Gera hash PBKDF2-HMAC-SHA256 com salt aleatório."""
    salt_hex = salt or secrets.token_hex(16)
    digest = hashlib.pbkdf2_hmac(
        "sha256",
        password.encode("utf-8"),
        bytes.fromhex(salt_hex),
        PBKDF2_ITERATIONS,
    ).hex()
    return f"{PBKDF2_PREFIX}${salt_hex}${digest}"


def verify_password(password: str, stored_value: str) -> tuple[bool, bool]:
    """Verifica senha contra valor armazenado.

    Retorna ``(valido, precisa_migrar)``, permitindo migrar senhas antigas em
    texto puro no próximo login bem-sucedido.
    """
    if stored_value.startswith(f"{PBKDF2_PREFIX}$"):
        parts = stored_value.split("$")
        if len(parts) != 3:
            return False, False
        _, salt_hex, expected_digest = parts
        try:
            salt_bytes = bytes.fromhex(salt_hex)
        except ValueError:
            return False, False
        candidate_digest = hashlib.pbkdf2_hmac(
            "sha256",
            password.encode("utf-8"),
            salt_bytes,
            PBKDF2_ITERATIONS,
        ).hex()
        return hmac.compare_digest(candidate_digest, expected_digest), False

    # Compatibilidade com registros legados em texto puro.
    return hmac.compare_digest(password, stored_value), True


def get_user_expense_file(username: str, base_dir: Path = BASE_DIR) -> Path:
    """Retorna o caminho seguro do arquivo CSV de despesas do usuário."""
    valid_user = validate_username(username)
    expenses_dir = get_expenses_dir(base_dir).resolve()
    target = (expenses_dir / f"{valid_user}.csv").resolve()
    if not target.is_relative_to(expenses_dir):
        raise ValidationError("Caminho de arquivo inválido para o usuário.")
    if not target.exists():
        target.write_text("", encoding="utf-8")
    return target


def _read_users(base_dir: Path = BASE_DIR) -> list[list[str]]:
    users_file = get_users_file(base_dir)
    rows: list[list[str]] = []
    with users_file.open("r", encoding="utf-8", newline="") as handle:
        reader = csv.reader(handle)
        for row in reader:
            if len(row) >= 2 and row[0].strip():
                rows.append([row[0].strip(), row[1]])
    return rows


def _write_users(rows: list[list[str]], base_dir: Path = BASE_DIR) -> None:
    users_file = get_users_file(base_dir)
    with users_file.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.writer(handle)
        writer.writerows(rows)


def user_exists(username: str, base_dir: Path = BASE_DIR) -> bool:
    """Verifica se um nome de usuário já está cadastrado (case-insensitive)."""
    cleaned = validate_username(username).casefold()
    return any(row[0].casefold() == cleaned for row in _read_users(base_dir))


def register_user(username: str, password: str, base_dir: Path = BASE_DIR) -> str:
    """Cadastra um novo usuário com senha hash e cria seu arquivo de despesas."""
    valid_user = validate_username(username)
    valid_password = validate_password(password)

    rows = _read_users(base_dir)
    if any(row[0].casefold() == valid_user.casefold() for row in rows):
        raise ValidationError("Este usuário já existe. Tente outro nome.")

    rows.append([valid_user, hash_password(valid_password)])
    _write_users(rows, base_dir)
    get_user_expense_file(valid_user, base_dir)
    return valid_user


def authenticate_user(username: str, password: str, base_dir: Path = BASE_DIR) -> bool:
    """Autentica um usuário e migra hash legado automaticamente se aplicável."""
    cleaned = username.strip()
    if not cleaned or not password:
        return False

    rows = _read_users(base_dir)
    for index, row in enumerate(rows):
        if row[0] == cleaned:
            valid, needs_migration = verify_password(password, row[1])
            if valid and needs_migration:
                rows[index][1] = hash_password(password)
                _write_users(rows, base_dir)
            return valid
    return False


def _read_raw_expense_rows(username: str, base_dir: Path = BASE_DIR) -> list[list[str]]:
    expense_file = get_user_expense_file(username, base_dir)
    rows: list[list[str]] = []
    with expense_file.open("r", encoding="utf-8", newline="") as handle:
        reader = csv.reader(handle)
        for row in reader:
            if row:
                rows.append(row)
    return rows


def _write_raw_expense_rows(
    username: str, rows: list[list[str]], base_dir: Path = BASE_DIR
) -> None:
    expense_file = get_user_expense_file(username, base_dir)
    with expense_file.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.writer(handle)
        writer.writerows(rows)


def _row_to_expense(row: list[str]) -> Expense | None:
    if len(row) < 4:
        return None
    try:
        amount = parse_amount(row[2])
    except ValidationError:
        return None
    return Expense(
        username=row[0].strip(),
        category=row[1].strip(),
        amount=amount,
        expense_date=row[3].strip(),
    )


def list_expenses(username: str, base_dir: Path = BASE_DIR) -> list[Expense]:
    """Lista todas as despesas válidas pertencentes ao usuário."""
    valid_user = validate_username(username)
    expenses: list[Expense] = []
    for row in _read_raw_expense_rows(valid_user, base_dir):
        expense = _row_to_expense(row)
        if expense and expense.username == valid_user:
            expenses.append(expense)
    return expenses


def add_expense(
    username: str,
    category: str,
    raw_amount: str,
    raw_date: str,
    base_dir: Path = BASE_DIR,
    *,
    default_month_key: str | None = None,
) -> Expense:
    """Valida e adiciona uma nova despesa ao arquivo do usuário."""
    valid_user = validate_username(username)
    valid_category = validate_category(category)
    valid_amount = parse_amount(raw_amount)
    valid_date = parse_date(raw_date, default_month_key=default_month_key)

    expense_file = get_user_expense_file(valid_user, base_dir)
    with expense_file.open("a", encoding="utf-8", newline="") as handle:
        writer = csv.writer(handle)
        writer.writerow([valid_user, valid_category, f"{valid_amount:.2f}", valid_date])

    return Expense(
        username=valid_user,
        category=valid_category,
        amount=valid_amount,
        expense_date=valid_date,
    )


def _locate_user_expense_indices(
    username: str, raw_rows: list[list[str]]
) -> list[int]:
    indices: list[int] = []
    for idx, row in enumerate(raw_rows):
        expense = _row_to_expense(row)
        if expense and expense.username == username:
            indices.append(idx)
    return indices


def update_expense(
    username: str,
    expense_index: int,
    category: str,
    raw_amount: str,
    raw_date: str,
    base_dir: Path = BASE_DIR,
    *,
    default_month_key: str | None = None,
) -> Expense:
    """Atualiza uma despesa do usuário pelo índice (base 0 na lista do usuário)."""
    valid_user = validate_username(username)
    valid_category = validate_category(category)
    valid_amount = parse_amount(raw_amount)
    valid_date = parse_date(raw_date, default_month_key=default_month_key)

    raw_rows = _read_raw_expense_rows(valid_user, base_dir)
    user_indices = _locate_user_expense_indices(valid_user, raw_rows)
    if expense_index < 0 or expense_index >= len(user_indices):
        raise ValidationError("Número de despesa inválido.")

    target_row_idx = user_indices[expense_index]
    raw_rows[target_row_idx] = [
        valid_user,
        valid_category,
        f"{valid_amount:.2f}",
        valid_date,
    ]
    _write_raw_expense_rows(valid_user, raw_rows, base_dir)

    return Expense(
        username=valid_user,
        category=valid_category,
        amount=valid_amount,
        expense_date=valid_date,
    )


def delete_expense(
    username: str, expense_index: int, base_dir: Path = BASE_DIR
) -> Expense:
    """Remove uma despesa do usuário pelo índice (base 0 na lista do usuário)."""
    valid_user = validate_username(username)
    raw_rows = _read_raw_expense_rows(valid_user, base_dir)
    user_indices = _locate_user_expense_indices(valid_user, raw_rows)
    if expense_index < 0 or expense_index >= len(user_indices):
        raise ValidationError("Número de despesa inválido.")

    target_row_idx = user_indices[expense_index]
    removed_row = raw_rows.pop(target_row_idx)
    removed_expense = _row_to_expense(removed_row)
    _write_raw_expense_rows(valid_user, raw_rows, base_dir)
    assert removed_expense is not None
    return removed_expense


def calculate_total(expenses: list[Expense]) -> Decimal:
    """Soma com precisão decimal os valores de uma lista de despesas."""
    return sum((item.amount for item in expenses), start=Decimal("0.00"))


def extract_month_key(expense_date: str) -> str | None:
    """Extrai a chave 'MM/AAAA' de uma data válida."""
    cleaned = expense_date.strip()
    try:
        parsed = datetime.strptime(cleaned, "%d/%m/%Y").date()
        return parsed.strftime("%m/%Y")
    except ValueError:
        return None


def format_month_label(month_key: str) -> str:
    """Formata '11/2026' como 'Nov/2026 (11/2026)' para exibição clara."""
    try:
        month_num, year_num = month_key.split("/")
        name = MONTH_NAMES_PT.get(int(month_num), month_num)
        return f"{name}/{year_num} ({month_key})"
    except ValueError:
        return month_key


def get_month_name(month_key: str) -> str:
    """Retorna o nome completo do mês em português para 'MM/AAAA'."""
    try:
        month_num, _ = month_key.split("/")
        return MONTH_FULL_NAMES_PT.get(int(month_num), month_key)
    except ValueError:
        return month_key


def format_month_full_label(month_key: str) -> str:
    """Formata '11/2026' como 'Novembro/2026'."""
    try:
        month_num, year_num = month_key.split("/")
        name = MONTH_FULL_NAMES_PT.get(int(month_num), month_num)
        return f"{name}/{year_num}"
    except ValueError:
        return month_key


def list_selectable_months(
    expenses: list[Expense], reference_date: date | None = None
) -> list[str]:
    """Retorna os 12 meses do ano atual mais quaisquer meses de outros anos com gastos."""
    ref = reference_date or date.today()
    keys: set[str] = {f"{m:02d}/{ref.year}" for m in range(1, 13)}
    for exp in expenses:
        key = extract_month_key(exp.expense_date)
        if key:
            keys.add(key)

    def _sort_key(mk: str) -> tuple[int, int]:
        month_str, year_str = mk.split("/")
        return -int(year_str), int(month_str)

    return sorted(keys, key=_sort_key)


def extract_year(expense_date: str) -> int | None:
    """Extrai o ano numérico de uma data 'DD/MM/AAAA'."""
    try:
        return datetime.strptime(expense_date.strip(), "%d/%m/%Y").date().year
    except ValueError:
        return None


def list_available_years(
    expenses: list[Expense], reference_date: date | None = None
) -> list[int]:
    """Retorna o ano atual e os anos presentes nas despesas, em ordem decrescente."""
    ref_year = (reference_date or date.today()).year
    years: set[int] = {ref_year}
    for exp in expenses:
        y = extract_year(exp.expense_date)
        if y is not None:
            years.add(y)
    return sorted(years, reverse=True)


def filter_expenses_by_year(expenses: list[Expense], year: int) -> list[Expense]:
    """Filtra despesas pertencentes a um ano específico."""
    return [exp for exp in expenses if extract_year(exp.expense_date) == year]


def summarize_year_by_month(
    expenses: list[Expense], year: int
) -> list[tuple[str, str, int, Decimal]]:
    """Retorna resumo dos 12 meses de um ano: (mm/aaaa, nome_mes, qtd, total)."""
    year_expenses = filter_expenses_by_year(expenses, year)
    grouped: dict[str, list[Expense]] = {}
    for exp in year_expenses:
        key = extract_month_key(exp.expense_date)
        if key:
            grouped.setdefault(key, []).append(exp)

    summary: list[tuple[str, str, int, Decimal]] = []
    for month_num in range(1, 13):
        key = f"{month_num:02d}/{year}"
        items = grouped.get(key, [])
        summary.append(
            (key, MONTH_FULL_NAMES_PT[month_num], len(items), calculate_total(items))
        )
    return summary


def list_available_months(expenses: list[Expense]) -> list[str]:
    """Retorna os meses distintos ('MM/AAAA') ordenados do mais recente ao mais antigo."""
    keys: set[str] = set()
    for exp in expenses:
        key = extract_month_key(exp.expense_date)
        if key:
            keys.add(key)

    def _sort_key(mk: str) -> tuple[int, int]:
        month_str, year_str = mk.split("/")
        return int(year_str), int(month_str)

    return sorted(keys, key=_sort_key, reverse=True)


def filter_expenses_by_month(
    expenses: list[Expense], month_key: str | None
) -> list[Expense]:
    """Filtra despesas por chave 'MM/AAAA' ou retorna todas se vazio."""
    if not month_key or month_key == "ALL":
        return list(expenses)
    return [exp for exp in expenses if extract_month_key(exp.expense_date) == month_key]


def calculate_monthly_average(expenses: list[Expense]) -> Decimal:
    """Calcula a média de gasto mensal entre os meses que possuem lançamentos."""
    if not expenses:
        return Decimal("0.00")

    totals_by_month: dict[str, Decimal] = {}
    for exp in expenses:
        key = extract_month_key(exp.expense_date) or "sem_data"
        totals_by_month[key] = totals_by_month.get(key, Decimal("0.00")) + exp.amount

    total = sum(totals_by_month.values(), start=Decimal("0.00"))
    average = total / Decimal(len(totals_by_month))
    return average.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)


def calculate_budget_status(spent: Decimal, salary: Decimal) -> tuple[Decimal, Decimal]:
    """Calcula saldo disponível e valor excedente/devendo frente ao salário."""
    available = max(Decimal("0.00"), salary - spent)
    debt = max(Decimal("0.00"), spent - salary)
    return (
        available.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP),
        debt.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP),
    )


def _get_salaries_file(base_dir: Path = BASE_DIR) -> Path:
    expenses_dir = get_expenses_dir(base_dir)
    salaries_file = expenses_dir / SALARIES_FILENAME
    if not salaries_file.exists():
        salaries_file.write_text("", encoding="utf-8")
    return salaries_file


def get_user_salary(username: str, base_dir: Path = BASE_DIR) -> Decimal:
    """Retorna o salário mensal configurado do usuário (ou R$ 0,00 se não definido)."""
    valid_user = validate_username(username)
    salaries_file = _get_salaries_file(base_dir)
    with salaries_file.open("r", encoding="utf-8", newline="") as handle:
        for row in csv.reader(handle):
            if len(row) >= 2 and row[0].strip() == valid_user:
                try:
                    return parse_salary(row[1])
                except ValidationError:
                    return Decimal("0.00")
    return Decimal("0.00")


def set_user_salary(
    username: str, raw_salary: str, base_dir: Path = BASE_DIR
) -> Decimal:
    """Salva o salário mensal do usuário com validação."""
    valid_user = validate_username(username)
    salary = parse_salary(raw_salary)
    salaries_file = _get_salaries_file(base_dir)

    rows: list[list[str]] = []
    updated = False
    with salaries_file.open("r", encoding="utf-8", newline="") as handle:
        for row in csv.reader(handle):
            if len(row) >= 2 and row[0].strip():
                if row[0].strip() == valid_user:
                    rows.append([valid_user, f"{salary:.2f}"])
                    updated = True
                else:
                    rows.append([row[0].strip(), row[1]])

    if not updated:
        rows.append([valid_user, f"{salary:.2f}"])

    with salaries_file.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.writer(handle)
        writer.writerows(rows)

    return salary


def _dpapi_protect(raw_bytes: bytes) -> bytes | None:
    if os.name != "nt":
        return None
    try:
        import ctypes
        import ctypes.wintypes as wt

        class _DataBlob(ctypes.Structure):
            _fields_ = [("cbData", wt.DWORD), ("pbData", ctypes.POINTER(ctypes.c_char))]

        crypt32 = ctypes.windll.crypt32  # type: ignore[attr-defined]
        kernel32 = ctypes.windll.kernel32  # type: ignore[attr-defined]
        in_blob = _DataBlob(len(raw_bytes), ctypes.create_string_buffer(raw_bytes, len(raw_bytes)))
        out_blob = _DataBlob()
        # CRYPTPROTECT_UI_FORBIDDEN = 0x1
        if not crypt32.CryptProtectData(
            ctypes.byref(in_blob), None, None, None, None, 0x1, ctypes.byref(out_blob)
        ):
            return None
        try:
            return ctypes.string_at(out_blob.pbData, out_blob.cbData)
        finally:
            kernel32.LocalFree(out_blob.pbData)
    except Exception:
        return None


def _dpapi_unprotect(cipher_bytes: bytes) -> bytes | None:
    if os.name != "nt":
        return None
    try:
        import ctypes
        import ctypes.wintypes as wt

        class _DataBlob(ctypes.Structure):
            _fields_ = [("cbData", wt.DWORD), ("pbData", ctypes.POINTER(ctypes.c_char))]

        crypt32 = ctypes.windll.crypt32  # type: ignore[attr-defined]
        kernel32 = ctypes.windll.kernel32  # type: ignore[attr-defined]
        in_blob = _DataBlob(
            len(cipher_bytes), ctypes.create_string_buffer(cipher_bytes, len(cipher_bytes))
        )
        out_blob = _DataBlob()
        if not crypt32.CryptUnprotectData(
            ctypes.byref(in_blob), None, None, None, None, 0x1, ctypes.byref(out_blob)
        ):
            return None
        try:
            return ctypes.string_at(out_blob.pbData, out_blob.cbData)
        finally:
            kernel32.LocalFree(out_blob.pbData)
    except Exception:
        return None


def _protect_session_token(token: str) -> str:
    raw = token.encode("utf-8")
    protected = _dpapi_protect(raw)
    if protected is not None:
        return f"dpapi:{base64.b64encode(protected).decode('ascii')}"
    return f"b64:{base64.b64encode(raw).decode('ascii')}"


def _unprotect_session_token(stored: str) -> str | None:
    if stored.startswith("dpapi:"):
        try:
            cipher = base64.b64decode(stored[6:], validate=True)
        except Exception:
            return None
        plain = _dpapi_unprotect(cipher)
        return plain.decode("utf-8") if plain else None
    if stored.startswith("b64:"):
        try:
            return base64.b64decode(stored[4:], validate=True).decode("utf-8")
        except Exception:
            return None
    return None


def save_session(username: str, base_dir: Path = BASE_DIR) -> None:
    """Salva um token de sessão local (sem senha) para login automático."""
    valid_user = validate_username(username)
    expenses_dir = get_expenses_dir(base_dir)
    session_file = expenses_dir / SESSION_FILENAME
    token = secrets.token_urlsafe(32)
    token_hash = hashlib.sha256(token.encode("utf-8")).hexdigest()
    protected = _protect_session_token(token)

    with session_file.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.writer(handle)
        writer.writerow([valid_user, token_hash, protected])


def load_saved_session(base_dir: Path = BASE_DIR) -> str | None:
    """Retorna o usuário da sessão salva caso o token e o cadastro sejam válidos."""
    session_file = get_expenses_dir(base_dir) / SESSION_FILENAME
    if not session_file.exists():
        return None

    with session_file.open("r", encoding="utf-8", newline="") as handle:
        for row in csv.reader(handle):
            if len(row) < 3:
                continue
            username, expected_hash, stored_token = row[0].strip(), row[1].strip(), row[2].strip()
            token = _unprotect_session_token(stored_token)
            if not token:
                return None
            actual_hash = hashlib.sha256(token.encode("utf-8")).hexdigest()
            if not hmac.compare_digest(actual_hash, expected_hash):
                return None
            try:
                if user_exists(username, base_dir):
                    return username
            except ValidationError:
                return None
    return None


def clear_saved_session(base_dir: Path = BASE_DIR) -> None:
    """Remove a sessão salva localmente."""
    session_file = get_expenses_dir(base_dir) / SESSION_FILENAME
    session_file.unlink(missing_ok=True)
