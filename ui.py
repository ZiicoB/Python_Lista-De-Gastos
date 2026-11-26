"""Componentes visuais TrueColor (paleta Holst) para o terminal/CMD."""

from __future__ import annotations

import os
import re
import sys

import storage

RGB = tuple[int, int, int]

# Paleta oficial "Holst"
PALETTE: dict[str, str] = {
    "deep": "#1E293B",
    "slate": "#334155",
    "sage": "#5C6B66",
    "taupe": "#8A7D7B",
    "rose": "#C8A99D",
    "cream": "#F2E6D6",
}

BG_DEEP: RGB = (30, 41, 59)       # #1E293B
BG_SLATE: RGB = (51, 65, 85)      # #334155
SAGE: RGB = (92, 107, 102)        # #5C6B66
TAUPE: RGB = (138, 125, 123)      # #8A7D7B
ROSE: RGB = (200, 169, 157)       # #C8A99D
CREAM: RGB = (242, 230, 214)      # #F2E6D6

RESET = "\033[0m"
BOLD = "\033[1m"
ANSI_RE = re.compile(r"\033\[[0-9;]*m")

CARD_WIDTH = 68
INNER_WIDTH = CARD_WIDTH - 2


def fg(color: RGB) -> str:
    """Retorna sequência ANSI TrueColor de primeiro plano."""
    return f"\033[38;2;{color[0]};{color[1]};{color[2]}m"


def bg(color: RGB) -> str:
    """Retorna sequência ANSI TrueColor de fundo."""
    return f"\033[48;2;{color[0]};{color[1]};{color[2]}m"


def style(
    text: str,
    *,
    fg_color: RGB | None = None,
    bg_color: RGB | None = None,
    bold: bool = False,
) -> str:
    """Aplica cores TrueColor e estilo ao texto sem vazar para fora do trecho."""
    codes: list[str] = []
    if bold:
        codes.append(BOLD)
    if fg_color is not None:
        codes.append(fg(fg_color))
    if bg_color is not None:
        codes.append(bg(bg_color))
    if not codes:
        return text
    return f"{''.join(codes)}{text}{RESET}"


def visible_len(text: str) -> int:
    """Calcula o comprimento visível ignorando sequências ANSI."""
    return len(ANSI_RE.sub("", text))


def strip_ansi(text: str) -> str:
    """Remove sequências ANSI mantendo apenas o texto visível."""
    return ANSI_RE.sub("", text)


def enable_cmd_support() -> None:
    """Habilita UTF-8 e sequências ANSI TrueColor no CMD do Windows."""
    try:
        if hasattr(sys.stdout, "reconfigure"):
            sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        if hasattr(sys.stdin, "reconfigure"):
            sys.stdin.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

    if os.name != "nt":
        return
    try:
        import ctypes

        kernel32 = ctypes.windll.kernel32  # type: ignore[attr-defined]
        kernel32.SetConsoleOutputCP(65001)
        kernel32.SetConsoleCP(65001)
        handle = kernel32.GetStdHandle(-11)
        mode = ctypes.c_ulong()
        if kernel32.GetConsoleMode(handle, ctypes.byref(mode)):
            kernel32.SetConsoleMode(handle, mode.value | 0x0004)
    except Exception:
        pass


def _fill_line(
    content: str,
    *,
    bg_color: RGB = BG_DEEP,
    border_color: RGB = TAUPE,
    left_pad: int = 2,
) -> str:
    """Formata uma linha dentro do cartão preservando largura exata de 68 colunas."""
    prefix = " " * left_pad
    body = f"{prefix}{content}"
    pad_needed = max(0, INNER_WIDTH - visible_len(body))
    # Reaplica bg_color antes dos preenchimentos para evitar falhas após RESETs internos.
    body_with_bg = body.replace(RESET, f"{RESET}{bg(bg_color)}")
    left_border = f"{bg(bg_color)}{fg(border_color)}│{RESET}"
    right_border = f"{bg(bg_color)}{fg(border_color)}│{RESET}"
    middle = f"{bg(bg_color)}{body_with_bg}{' ' * pad_needed}{RESET}"
    return f"{left_border}{middle}{right_border}"


def _divider(
    *,
    left: str = "├",
    right: str = "┤",
    fill: str = "─",
    bg_color: RGB = BG_DEEP,
    border_color: RGB = TAUPE,
) -> str:
    return f"{bg(bg_color)}{fg(border_color)}{left}{fill * INNER_WIDTH}{right}{RESET}"


def render_brand_banner() -> str:
    """Renderiza o cabeçalho principal com a identidade visual Holst."""
    swatch = "".join(
        f"{bg(color)}  {RESET}"
        for color in (BG_DEEP, BG_SLATE, SAGE, TAUPE, ROSE, CREAM)
    )
    title = style("✦  LISTA DE GASTOS", fg_color=ROSE, bg_color=BG_DEEP, bold=True)
    subtitle = style("Controle Financeiro", fg_color=TAUPE, bg_color=BG_DEEP)
    gap = max(1, INNER_WIDTH - 4 - visible_len(title) - visible_len(subtitle) - visible_len(swatch))
    top_line = f"{title}  {style('•', fg_color=TAUPE, bg_color=BG_DEEP)}  {subtitle}{' ' * max(1, gap - 5)}{swatch}"
    lines = [
        _divider(left="╭", right="╮", bg_color=BG_DEEP),
        _fill_line(top_line, bg_color=BG_DEEP),
        _divider(left="╰", right="╯", bg_color=BG_DEEP),
    ]
    return "\n".join(lines)


def render_card(
    title: str,
    body_lines: list[str],
    *,
    subtitle: str | None = None,
    footer_lines: list[str] | None = None,
) -> str:
    """Renderiza um cartão organizado usando a paleta Holst."""
    output: list[str] = [
        _divider(left="╭", right="╮", bg_color=BG_SLATE),
        _fill_line(
            style(title.upper(), fg_color=ROSE, bg_color=BG_SLATE, bold=True),
            bg_color=BG_SLATE,
        ),
    ]

    if subtitle:
        output.append(
            _fill_line(
                style(subtitle, fg_color=CREAM, bg_color=BG_SLATE),
                bg_color=BG_SLATE,
            )
        )

    output.append(_divider(left="├", right="┤", bg_color=BG_DEEP))
    output.append(_fill_line("", bg_color=BG_DEEP))

    for line in body_lines:
        output.append(_fill_line(line, bg_color=BG_DEEP))

    output.append(_fill_line("", bg_color=BG_DEEP))

    if footer_lines:
        output.append(_divider(left="├", right="┤", bg_color=BG_SLATE))
        for fline in footer_lines:
            output.append(_fill_line(fline, bg_color=BG_SLATE))

    output.append(_divider(left="╰", right="╯", bg_color=BG_SLATE if footer_lines else BG_DEEP))
    return "\n".join(output)


def render_menu_option(key: str, label: str, hint: str = "") -> str:
    """Formata uma opção de menu com tecla em destaque."""
    key_badge = style(f" [{key}] ", fg_color=ROSE, bg_color=BG_SLATE, bold=True)
    text = style(label, fg_color=CREAM, bg_color=BG_DEEP)
    if not hint:
        return f"{key_badge}  {text}"
    hint_text = style(hint, fg_color=TAUPE, bg_color=BG_DEEP)
    avail = INNER_WIDTH - 4 - visible_len(key_badge) - 2 - visible_len(text) - visible_len(hint_text)
    spacer = " " * max(2, avail)
    return f"{key_badge}  {text}{spacer}{hint_text}"


def render_alert(message: str, *, kind: str = "info") -> str:
    """Renderiza uma faixa de aviso alinhada ao cartão."""
    if kind == "success":
        icon = style(" ✓ ", fg_color=CREAM, bg_color=SAGE, bold=True)
        msg = style(message, fg_color=CREAM, bg_color=BG_DEEP, bold=True)
        border = SAGE
    elif kind == "error":
        icon = style(" ! ", fg_color=BG_DEEP, bg_color=ROSE, bold=True)
        msg = style(message, fg_color=ROSE, bg_color=BG_DEEP, bold=True)
        border = ROSE
    else:
        icon = style(" • ", fg_color=CREAM, bg_color=BG_SLATE, bold=True)
        msg = style(message, fg_color=CREAM, bg_color=BG_DEEP)
        border = TAUPE

    lines = [
        _divider(left="╭", right="╮", bg_color=BG_DEEP, border_color=border),
        _fill_line(f"{icon}  {msg}", bg_color=BG_DEEP, border_color=border),
        _divider(left="╰", right="╯", bg_color=BG_DEEP, border_color=border),
    ]
    return "\n".join(lines)


def render_expenses_table(
    expenses: list[storage.Expense],
    *,
    numbered: bool = False,
) -> list[str]:
    """Gera linhas formatadas de tabela de despesas para compor um cartão."""
    cat_width = 25 if numbered else 31
    sep = style(" │ ", fg_color=TAUPE, bg_color=BG_DEEP)
    header_sep = style(" │ ", fg_color=TAUPE, bg_color=BG_SLATE)

    col_cat = f"{'Categoria':<{cat_width}}"
    col_val = f"{'Valor':<15}"
    col_dat = f"{'Data':<10}"

    if numbered:
        header = (
            f"{style(' # ', fg_color=ROSE, bg_color=BG_SLATE, bold=True)}"
            f"{header_sep}"
            f"{style(col_cat, fg_color=ROSE, bg_color=BG_SLATE, bold=True)}"
            f"{header_sep}"
            f"{style(col_val, fg_color=ROSE, bg_color=BG_SLATE, bold=True)}"
            f"{header_sep}"
            f"{style(col_dat, fg_color=ROSE, bg_color=BG_SLATE, bold=True)}"
        )
    else:
        header = (
            f"{style(col_cat, fg_color=ROSE, bg_color=BG_SLATE, bold=True)}"
            f"{header_sep}"
            f"{style(col_val, fg_color=ROSE, bg_color=BG_SLATE, bold=True)}"
            f"{header_sep}"
            f"{style(col_dat, fg_color=ROSE, bg_color=BG_SLATE, bold=True)}"
        )

    header_pad = max(0, (INNER_WIDTH - 4) - visible_len(header))
    header = f"{header}{style(' ' * header_pad, bg_color=BG_SLATE)}"
    rule = style("─" * (INNER_WIDTH - 4), fg_color=TAUPE, bg_color=BG_DEEP)
    rows: list[str] = [header, rule]

    for index, expense in enumerate(expenses, start=1):
        cat_txt = expense.category.upper()[:cat_width]
        val_txt = f"R$ {expense.amount:.2f}"
        date_txt = expense.expense_date

        cat_cell = style(f"{cat_txt:<{cat_width}}", fg_color=CREAM, bg_color=BG_DEEP)
        val_cell = style(f"{val_txt:<15}", fg_color=ROSE, bg_color=BG_DEEP, bold=True)
        date_cell = style(f"{date_txt:<10}", fg_color=TAUPE, bg_color=BG_DEEP)

        if numbered:
            idx_cell = style(f"{index:>2} ", fg_color=SAGE, bg_color=BG_DEEP, bold=True)
            rows.append(f"{idx_cell}{sep}{cat_cell}{sep}{val_cell}{sep}{date_cell}")
        else:
            rows.append(f"{cat_cell}{sep}{val_cell}{sep}{date_cell}")

    return rows


def format_prompt(label: str) -> str:
    """Estiliza o prompt de entrada para o CMD."""
    arrow = style("›", fg_color=ROSE, bold=True)
    text = style(label, fg_color=CREAM, bold=True)
    return f"\n{arrow} {text}"
