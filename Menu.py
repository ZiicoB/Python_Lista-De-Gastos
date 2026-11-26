"""Interface de linha de comando (CMD) do sistema Lista de Gastos."""

from __future__ import annotations

import getpass
import os
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable

import storage
import ui


def enable_windows_ansi() -> None:
    """Mantido por compatibilidade; delega para o suporte completo de CMD."""
    ui.enable_cmd_support()


def clear_screen() -> None:
    """Limpa o terminal de forma compatível com Windows e Unix."""
    os.system("cls" if os.name == "nt" else "clear")


@dataclass
class ConsoleIO:
    """Abstração de entrada/saída para uso no CMD e em testes automatizados."""

    input_fn: Callable[[str], str] = input
    password_fn: Callable[[str], str] = getpass.getpass
    output_fn: Callable[[str], None] = print
    clear_fn: Callable[[], None] = clear_screen
    base_dir: Path = field(default_factory=lambda: storage.BASE_DIR)


def _render_screen(
    io: ConsoleIO,
    card_title: str,
    body_lines: list[str],
    *,
    subtitle: str | None = None,
    footer_lines: list[str] | None = None,
    alert: tuple[str, str] | None = None,
) -> None:
    """Limpa a tela e desenha banner, alerta opcional e cartão principal."""
    io.clear_fn()
    io.output_fn(ui.render_brand_banner())
    if alert is not None:
        message, kind = alert
        io.output_fn(ui.render_alert(message, kind=kind))
    io.output_fn(
        ui.render_card(
            card_title,
            body_lines,
            subtitle=subtitle,
            footer_lines=footer_lines,
        )
    )


def _prompt_valid(
    io: ConsoleIO,
    prompt_text: str,
    validator: Callable[[str], object],
    *,
    allow_cancel: bool = False,
    secret: bool = False,
):
    """Solicita entrada até passar na validação ou ser cancelada com '0'."""
    reader = io.password_fn if secret else io.input_fn
    styled_prompt = ui.format_prompt(prompt_text)
    while True:
        raw = reader(styled_prompt)
        if allow_cancel and raw.strip() == "0":
            return None
        try:
            return validator(raw)
        except storage.ValidationError as exc:
            io.output_fn(ui.render_alert(str(exc), kind="error"))


def main(io: ConsoleIO | None = None) -> None:
    """Executa o loop do menu principal com tema Holst para CMD."""
    console = io or ConsoleIO()
    ui.enable_cmd_support()
    alert: tuple[str, str] | None = None

    while True:
        body = [
            ui.render_menu_option("1", "Login do Usuário", "Acessar sua carteira"),
            ui.render_menu_option("2", "Criar novo Usuário", "Cadastrar nova conta"),
            ui.render_menu_option("0", "Encerrar sistema", "Sair com segurança"),
        ]
        _render_screen(
            console,
            "Menu Principal",
            body,
            subtitle="Escolha uma opção para começar",
            alert=alert,
        )
        alert = None

        opcao = console.input_fn(ui.format_prompt("Digite sua opção: ")).strip()

        if opcao == "1":
            login_usuario(console)
        elif opcao == "2":
            created = novo_usuario(console)
            if created:
                alert = ("Novo usuário criado com sucesso!", "success")
        elif opcao == "0":
            console.clear_fn()
            console.output_fn(ui.render_brand_banner())
            console.output_fn(ui.render_alert("SISTEMA ENCERRADO.", kind="info"))
            console.output_fn(ui.render_alert("Dados salvos com sucesso!", kind="success"))
            return
        else:
            alert = ("Opção inválida.", "error")


def login_usuario(io: ConsoleIO | None = None) -> None:
    """Realiza autenticação de usuário e encaminha ao menu do cliente."""
    console = io or ConsoleIO()
    alert: tuple[str, str] | None = None

    while True:
        body = [
            ui.style("Informe suas credenciais de acesso.", fg_color=ui.CREAM, bg_color=ui.BG_DEEP),
            ui.style("Digite 0 no login para voltar ao menu principal.", fg_color=ui.TAUPE, bg_color=ui.BG_DEEP),
        ]
        _render_screen(
            console,
            "Sistema de Login",
            body,
            subtitle="Autenticação segura",
            alert=alert,
        )
        alert = None

        nick = console.input_fn(ui.format_prompt("Seu login: ")).strip()
        if nick == "0":
            return
        if not nick:
            alert = ("Informe um nome de usuário.", "error")
            continue

        senha = console.password_fn(ui.format_prompt("Digite sua senha: "))

        if storage.authenticate_user(nick, senha, console.base_dir):
            menu_cliente(nick, console)
            return

        error_body = [
            ui.render_menu_option("1", "Tentar novamente", "Digitar outro login"),
            ui.render_menu_option("2", "Criar novo Usuário", "Abrir tela de cadastro"),
            ui.render_menu_option("0", "Voltar", "Menu principal"),
        ]
        error_alert: tuple[str, str] = ("Usuário ou senha inválidos.", "error")

        while True:
            _render_screen(
                console,
                "Falha na Autenticação",
                error_body,
                subtitle="Verifique seu usuário e senha",
                alert=error_alert,
            )
            escolha = console.input_fn(ui.format_prompt("Digite sua opção: ")).strip()
            if escolha == "1":
                break
            if escolha == "2":
                if novo_usuario(console):
                    alert = ("Novo usuário criado com sucesso!", "success")
                break
            if escolha == "0":
                return
            error_alert = ("Opção inválida.", "error")


def novo_usuario(io: ConsoleIO | None = None) -> bool:
    """Cadastra um novo usuário validando unicidade e segurança da senha."""
    console = io or ConsoleIO()
    alert: tuple[str, str] | None = None

    while True:
        body = [
            ui.style("• Usuário: 2 a 32 caracteres (letras, números, '_' ou '-').", fg_color=ui.CREAM, bg_color=ui.BG_DEEP),
            ui.style("• Senha: mínimo de 4 caracteres (oculta na digitação).", fg_color=ui.CREAM, bg_color=ui.BG_DEEP),
            ui.style("• Digite 0 para cancelar e voltar.", fg_color=ui.TAUPE, bg_color=ui.BG_DEEP),
        ]
        _render_screen(
            console,
            "Novo Usuário",
            body,
            subtitle="Cadastro de conta",
            alert=alert,
        )
        alert = None

        novo_nick = _prompt_valid(
            console,
            "Novo usuário: ",
            storage.validate_username,
            allow_cancel=True,
        )
        if novo_nick is None:
            return False

        if storage.user_exists(novo_nick, console.base_dir):
            alert = ("Este usuário já existe. Tente outro nome!", "error")
            continue

        nova_senha = _prompt_valid(
            console,
            "Senha (mín. 4 caracteres, ou 0 para cancelar): ",
            storage.validate_password,
            allow_cancel=True,
            secret=True,
        )
        if nova_senha is None:
            return False

        confirmacao = console.password_fn(ui.format_prompt("Confirme a senha: "))
        if nova_senha != confirmacao:
            alert = ("As senhas não coincidem.", "error")
            continue

        try:
            storage.register_user(novo_nick, nova_senha, console.base_dir)
        except storage.ValidationError as exc:
            alert = (str(exc), "error")
            continue

        console.output_fn(ui.render_alert("Novo usuário criado com sucesso!", kind="success"))
        return True


def menu_cliente(nick: str, io: ConsoleIO | None = None) -> None:
    """Exibe o painel e menu principal do usuário autenticado."""
    console = io or ConsoleIO()
    storage.get_user_expense_file(nick, console.base_dir)
    alert: tuple[str, str] | None = None

    while True:
        expenses = storage.list_expenses(nick, console.base_dir)
        total = storage.calculate_total(expenses)

        badge_user = ui.style(f" ● {nick} ", fg_color=ui.CREAM, bg_color=ui.SAGE, bold=True)
        count_txt = ui.style(f"Registros: {len(expenses)}", fg_color=ui.CREAM, bg_color=ui.BG_DEEP)
        total_txt = ui.style(f"Total: R$ {total:.2f}", fg_color=ui.ROSE, bg_color=ui.BG_DEEP, bold=True)

        body = [
            f"{badge_user}   {count_txt}   {ui.style('•', fg_color=ui.TAUPE, bg_color=ui.BG_DEEP)}   {total_txt}",
            ui.style("─" * (ui.INNER_WIDTH - 4), fg_color=ui.TAUPE, bg_color=ui.BG_DEEP),
            ui.render_menu_option("1", "Adicionar Despesa", "Registrar novo gasto"),
            ui.render_menu_option("2", "Editar Despesa", "Alterar ou excluir item"),
            ui.render_menu_option("3", "Mostrar Despesas", "Relatório e total"),
            ui.render_menu_option("0", "Sair do Usuário", "Trocar de conta"),
        ]
        _render_screen(
            console,
            f"Painel do Usuário — {nick}",
            body,
            subtitle="Gerencie suas despesas pessoais",
            alert=alert,
        )
        alert = None

        opcao = console.input_fn(ui.format_prompt("Digite sua opção: ")).strip()

        if opcao == "1":
            adicionar_despesa(nick, console)
        elif opcao == "2":
            editar_despesa(nick, console)
        elif opcao == "3":
            mostrar_despesa(nick, console)
        elif opcao == "0":
            return
        else:
            alert = ("Opção inválida.", "error")


def adicionar_despesa(nick: str, io: ConsoleIO | None = None) -> None:
    """Adiciona uma ou mais despesas validadas para o usuário."""
    console = io or ConsoleIO()

    while True:
        body = [
            ui.style("Preencha os dados do lançamento:", fg_color=ui.CREAM, bg_color=ui.BG_DEEP),
            ui.style("• Categoria: nome ou local da despesa", fg_color=ui.TAUPE, bg_color=ui.BG_DEEP),
            ui.style("• Valor: positivo com '.' ou ',' (ex: 45.90)", fg_color=ui.TAUPE, bg_color=ui.BG_DEEP),
            ui.style("• Data: DD/MM ou DD/MM/AAAA", fg_color=ui.TAUPE, bg_color=ui.BG_DEEP),
            ui.style("• Digite 0 em qualquer campo para voltar.", fg_color=ui.TAUPE, bg_color=ui.BG_DEEP),
        ]
        _render_screen(
            console,
            "Nova Despesa",
            body,
            subtitle=f"Usuário: {nick}",
        )

        categoria = _prompt_valid(
            console,
            "Tipo de Despesa: ",
            storage.validate_category,
            allow_cancel=True,
        )
        if categoria is None:
            return

        valor = _prompt_valid(
            console,
            "Valor (ex: 45.90, ou 0 para cancelar): ",
            storage.parse_amount,
            allow_cancel=True,
        )
        if valor is None:
            return

        data_gasto = _prompt_valid(
            console,
            "Data (DD/MM/AAAA, ou 0 para cancelar): ",
            storage.parse_date,
            allow_cancel=True,
        )
        if data_gasto is None:
            return

        storage.add_expense(nick, categoria, str(valor), data_gasto, console.base_dir)
        sub_alert: tuple[str, str] = ("Despesa adicionada com sucesso!", "success")

        while True:
            sub_body = [
                ui.render_menu_option("1", "Adicionar novamente", "Lançar outro gasto"),
                ui.render_menu_option("0", "Voltar", "Retornar ao painel"),
            ]
            _render_screen(
                console,
                "Nova Despesa",
                sub_body,
                subtitle=f"Último item: {categoria.upper()} — R$ {valor:.2f}",
                alert=sub_alert,
            )
            repetir = console.input_fn(ui.format_prompt("Digite sua opção: ")).strip()
            if repetir == "1":
                break
            if repetir == "0":
                return
            sub_alert = ("Opção inválida.", "error")


def editar_despesa(nick: str, io: ConsoleIO | None = None) -> None:
    """Permite alterar ou remover uma despesa existente do usuário."""
    console = io or ConsoleIO()
    alert: tuple[str, str] | None = None

    while True:
        expenses = storage.list_expenses(nick, console.base_dir)
        if not expenses:
            _render_screen(
                console,
                "Editar Despesas",
                [ui.style("Nenhuma despesa cadastrada.", fg_color=ui.TAUPE, bg_color=ui.BG_DEEP)],
                subtitle=f"Usuário: {nick}",
                alert=alert,
            )
            console.input_fn(ui.format_prompt("Pressione Enter para voltar..."))
            return

        table_lines = ui.render_expenses_table(expenses, numbered=True)
        _render_screen(
            console,
            "Editar Despesas",
            table_lines,
            subtitle=f"Usuário: {nick} • {len(expenses)} lançamento(s)",
            footer_lines=[
                ui.style(
                    "Digite o número do item para editar ou Enter para voltar.",
                    fg_color=ui.CREAM,
                    bg_color=ui.BG_SLATE,
                )
            ],
            alert=alert,
        )
        alert = None

        escolha = console.input_fn(
            ui.format_prompt("Número da despesa (Enter para voltar): ")
        ).strip()
        if escolha == "":
            return

        try:
            idx = int(escolha) - 1
        except ValueError:
            alert = ("Digite um número válido.", "error")
            continue

        if idx < 0 or idx >= len(expenses):
            alert = ("Número de despesa fora da lista.", "error")
            continue

        selected = expenses[idx]
        action_body = [
            ui.style(
                f"Selecionado: #{idx + 1} — {selected.category.upper()} | R$ {selected.amount:.2f} | {selected.expense_date}",
                fg_color=ui.ROSE,
                bg_color=ui.BG_DEEP,
                bold=True,
            ),
            ui.style("─" * (ui.INNER_WIDTH - 4), fg_color=ui.TAUPE, bg_color=ui.BG_DEEP),
            ui.render_menu_option("1", "Alterar", "Atualizar categoria, valor e data"),
            ui.render_menu_option("2", "Deletar", "Remover lançamento"),
            ui.render_menu_option("0", "Voltar", "Escolher outra despesa"),
        ]
        _render_screen(
            console,
            "Ação na Despesa",
            action_body,
            subtitle=f"Usuário: {nick}",
        )

        acao = console.input_fn(ui.format_prompt("Qual sua opção: ")).strip()

        if acao == "1":
            nova_categoria = _prompt_valid(
                console,
                "Novo nome da categoria (ou 0 para cancelar): ",
                storage.validate_category,
                allow_cancel=True,
            )
            if nova_categoria is None:
                continue

            novo_valor = _prompt_valid(
                console,
                "Novo valor (ou 0 para cancelar): ",
                storage.parse_amount,
                allow_cancel=True,
            )
            if novo_valor is None:
                continue

            nova_data = _prompt_valid(
                console,
                "Nova data (DD/MM/AAAA, ou 0 para cancelar): ",
                storage.parse_date,
                allow_cancel=True,
            )
            if nova_data is None:
                continue

            storage.update_expense(
                nick,
                idx,
                nova_categoria,
                str(novo_valor),
                nova_data,
                console.base_dir,
            )
            alert = ("Despesa atualizada com sucesso!", "success")
        elif acao == "2":
            confirmar = (
                console.input_fn(ui.format_prompt("Confirmar exclusão? (s/N): "))
                .strip()
                .lower()
            )
            if confirmar == "s":
                storage.delete_expense(nick, idx, console.base_dir)
                alert = ("Despesa deletada com sucesso!", "success")
            else:
                alert = ("Exclusão cancelada.", "info")
        elif acao == "0":
            continue
        else:
            alert = ("Opção inválida.", "error")


def mostrar_despesa(nick: str, io: ConsoleIO | None = None) -> None:
    """Exibe todas as despesas do usuário e o total acumulado."""
    console = io or ConsoleIO()
    expenses = storage.list_expenses(nick, console.base_dir)

    if not expenses:
        _render_screen(
            console,
            "Total Despesas",
            [ui.style("Nenhuma despesa cadastrada.", fg_color=ui.TAUPE, bg_color=ui.BG_DEEP)],
            subtitle=f"Usuário: {nick}",
        )
    else:
        table_lines = ui.render_expenses_table(expenses, numbered=False)
        total = storage.calculate_total(expenses)
        monthly_avg = storage.calculate_monthly_average(expenses)
        total_line = ui.style(
            f"Despesas totais: R$ {total:.2f}  •  Média mensal: {storage.format_brl(monthly_avg)}",
            fg_color=ui.ROSE,
            bg_color=ui.BG_SLATE,
            bold=True,
        )
        _render_screen(
            console,
            "Total Despesas",
            table_lines,
            subtitle=f"Usuário: {nick} • {len(expenses)} lançamento(s)",
            footer_lines=[total_line],
        )

    console.input_fn(ui.format_prompt("Pressione Enter para voltar..."))


if __name__ == "__main__":
    if "--cli" in sys.argv[1:]:
        main()
    else:
        import app_gui

        app_gui.launch()
