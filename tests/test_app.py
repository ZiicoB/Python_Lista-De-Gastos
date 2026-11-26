"""Testes unitários e de fluxo CLI para o sistema Lista de Gastos."""

from __future__ import annotations

import tempfile
import tkinter as tk
import unittest
from datetime import date
from decimal import Decimal
from pathlib import Path

import app_gui
import Menu
import storage
import ui


class StorageTests(unittest.TestCase):
    """Testes da camada de persistência, validação e segurança."""

    def setUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory()
        self.base_dir = Path(self.temp_dir.name)

    def tearDown(self) -> None:
        self.temp_dir.cleanup()

    def test_register_prevents_duplicates_and_hashes_password(self) -> None:
        storage.register_user("alice", "segredo1", self.base_dir)
        storage.register_user("bob", "segredo2", self.base_dir)

        with self.assertRaises(storage.ValidationError):
            storage.register_user("alice", "outrasenha", self.base_dir)
        with self.assertRaises(storage.ValidationError):
            storage.register_user("Alice", "outrasenha", self.base_dir)

        users_content = (self.base_dir / "Usuarios.csv").read_text(encoding="utf-8")
        lines = users_content.strip().splitlines()
        self.assertEqual(len(lines), 2)
        self.assertNotIn("segredo1", users_content)
        self.assertNotIn("segredo2", users_content)
        self.assertTrue(lines[0].startswith("alice,pbkdf2_sha256$"))

    def test_authenticate_existing_nonexistent_and_legacy_migration(self) -> None:
        users_file = storage.get_users_file(self.base_dir)
        # Simula registro legado em texto puro sem quebra de linha final
        users_file.write_text("legado,1234", encoding="utf-8")

        self.assertFalse(storage.authenticate_user("inexistente", "1234", self.base_dir))
        self.assertFalse(storage.authenticate_user("legado", "errada", self.base_dir))
        self.assertTrue(storage.authenticate_user("legado", "1234", self.base_dir))

        migrated = users_file.read_text(encoding="utf-8")
        self.assertIn("pbkdf2_sha256$", migrated)
        self.assertNotIn(",1234", migrated)

        # Novo usuário após arquivo legado não colide na mesma linha
        storage.register_user("maria", "4321", self.base_dir)
        self.assertEqual(len(users_file.read_text(encoding="utf-8").splitlines()), 2)
        self.assertTrue(storage.authenticate_user("maria", "4321", self.base_dir))

    def test_username_path_traversal_and_invalid_chars_blocked(self) -> None:
        for invalid in ["", "a", "../fora", "user/name", "user,1", "user name", "a*b"]:
            with self.subTest(username=invalid):
                with self.assertRaises(storage.ValidationError):
                    storage.validate_username(invalid)

    def test_amount_and_date_validation(self) -> None:
        self.assertEqual(storage.parse_amount("10,50"), Decimal("10.50"))
        self.assertEqual(storage.parse_amount("20.1"), Decimal("20.10"))

        for bad_amount in ["", "0", "-5", "abc", "NaN", "Infinity"]:
            with self.subTest(amount=bad_amount):
                with self.assertRaises(storage.ValidationError):
                    storage.parse_amount(bad_amount)

        self.assertEqual(
            storage.parse_date("29/02/2024"),
            "29/02/2024",
        )
        self.assertEqual(
            storage.parse_date("15/08", today=date(2026, 11, 25)),
            "15/08/2026",
        )
        self.assertEqual(
            storage.parse_date("29/02", today=date(2024, 2, 1)),
            "29/02/2024",
        )

        for bad_date in ["", "515", "21/21/21", "29/02/2025", "31/04/2026"]:
            with self.subTest(date=bad_date):
                with self.assertRaises(storage.ValidationError):
                    storage.parse_date(bad_date)
        with self.assertRaises(storage.ValidationError):
            storage.parse_date("29/02", today=date(2026, 2, 1))

    def test_expenses_crud_csv_commas_and_user_filtering(self) -> None:
        storage.register_user("joao", "senha123", self.base_dir)

        storage.add_expense("joao", "Alimentação, Bar", "10,10", "01/11/2026", self.base_dir)
        storage.add_expense("joao", "Transporte", "20.20", "02/11/2026", self.base_dir)

        # Injeta linha de outro usuário e linha malformada para testar isolamento
        expense_file = storage.get_user_expense_file("joao", self.base_dir)
        with expense_file.open("a", encoding="utf-8", newline="") as handle:
            handle.write("outro,Invasao,999.00,03/11/2026\n")
            handle.write("linha_corrompida\n")

        joao_expenses = storage.list_expenses("joao", self.base_dir)
        self.assertEqual(len(joao_expenses), 2)
        self.assertEqual(joao_expenses[0].category, "Alimentação, Bar")
        self.assertEqual(storage.calculate_total(joao_expenses), Decimal("30.30"))

        storage.update_expense("joao", 1, "Metrô", "15.50", "05/11/2026", self.base_dir)
        updated = storage.list_expenses("joao", self.base_dir)
        self.assertEqual(updated[1].category, "Metrô")
        self.assertEqual(updated[1].amount, Decimal("15.50"))

        removed = storage.delete_expense("joao", 0, self.base_dir)
        self.assertEqual(removed.category, "Alimentação, Bar")
        remaining = storage.list_expenses("joao", self.base_dir)
        self.assertEqual(len(remaining), 1)
        self.assertEqual(remaining[0].category, "Metrô")

        # Linha de outro usuário permanece intacta no arquivo
        raw_text = expense_file.read_text(encoding="utf-8")
        self.assertIn("outro,Invasao,999.00,03/11/2026", raw_text)

    def test_currency_formatting_monthly_average_salary_and_debt(self) -> None:
        self.assertEqual(storage.format_currency_from_digits("25"), "R$ 0,25")
        self.assertEqual(storage.format_currency_from_digits("2500"), "R$ 25,00")
        self.assertEqual(storage.format_currency_from_digits("123456"), "R$ 1.234,56")
        self.assertEqual(storage.parse_amount("R$ 1.234,56"), Decimal("1234.56"))
        self.assertEqual(storage.parse_amount("R$ 0,25"), Decimal("0.25"))

        storage.register_user("lucas", "senha123", self.base_dir)
        storage.add_expense("lucas", "Mercado", "R$ 100,00", "10/10/2026", self.base_dir)
        storage.add_expense("lucas", "Luz", "R$ 200,00", "15/11/2026", self.base_dir)
        storage.add_expense("lucas", "Internet", "R$ 150,00", "20/11/2026", self.base_dir)

        all_exp = storage.list_expenses("lucas", self.base_dir)
        self.assertEqual(storage.list_available_months(all_exp), ["11/2026", "10/2026"])
        self.assertEqual(len(storage.filter_expenses_by_month(all_exp, "11/2026")), 2)
        # Média mensal: (100 [out] + 350 [nov]) / 2 = 225.00
        self.assertEqual(storage.calculate_monthly_average(all_exp), Decimal("225.00"))

        storage.set_user_salary("lucas", "R$ 300,00", self.base_dir)
        self.assertEqual(storage.get_user_salary("lucas", self.base_dir), Decimal("300.00"))

        # Em 11/2026 gastou 350 > salário 300 => deve 50,00
        nov_total = storage.calculate_total(storage.filter_expenses_by_month(all_exp, "11/2026"))
        avail, debt = storage.calculate_budget_status(nov_total, Decimal("300.00"))
        self.assertEqual(avail, Decimal("0.00"))
        self.assertEqual(debt, Decimal("50.00"))

        # Resumo anual de 12 meses
        self.assertEqual(storage.get_month_name("11/2026"), "Novembro")
        self.assertEqual(storage.format_month_full_label("11/2026"), "Novembro/2026")
        summary = storage.summarize_year_by_month(all_exp, 2026)
        self.assertEqual(len(summary), 12)
        self.assertEqual(summary[9], ("10/2026", "Outubro", 1, Decimal("100.00")))
        self.assertEqual(summary[10], ("11/2026", "Novembro", 2, Decimal("350.00")))

    def test_saved_session_token_security_and_clear(self) -> None:
        storage.register_user("patricia", "minhasenha", self.base_dir)
        storage.save_session("patricia", self.base_dir)

        session_content = (self.base_dir / "Arquivos" / "sessao.csv").read_text(encoding="utf-8")
        self.assertNotIn("minhasenha", session_content)
        self.assertEqual(storage.load_saved_session(self.base_dir), "patricia")

        # Adulteração do hash invalida a sessão
        parts = session_content.strip().split(",")
        (self.base_dir / "Arquivos" / "sessao.csv").write_text(
            f"{parts[0]},{'0' * 64},{parts[2]}\n", encoding="utf-8"
        )
        self.assertIsNone(storage.load_saved_session(self.base_dir))

        storage.save_session("patricia", self.base_dir)
        storage.clear_saved_session(self.base_dir)
        self.assertIsNone(storage.load_saved_session(self.base_dir))


class CLIFlowTests(unittest.TestCase):
    """Testes de fluxo interativo na CLI sem recursão infinita."""

    def setUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory()
        self.base_dir = Path(self.temp_dir.name)

    def tearDown(self) -> None:
        self.temp_dir.cleanup()

    def _run_cli(self, inputs: list[str], passwords: list[str]) -> list[str]:
        input_iter = iter(inputs)
        pass_iter = iter(passwords)
        outputs: list[str] = []

        io = Menu.ConsoleIO(
            input_fn=lambda _prompt: next(input_iter),
            password_fn=lambda _prompt: next(pass_iter),
            output_fn=outputs.append,
            clear_fn=lambda: None,
            base_dir=self.base_dir,
        )
        Menu.main(io)
        return outputs

    def test_full_user_lifecycle_cli(self) -> None:
        outputs = self._run_cli(
            inputs=[
                "9",          # opção inválida no menu principal
                "2",          # criar novo usuário
                "ana",        # novo usuário
                "1",          # login
                "ana",        # login
                "1",          # adicionar despesa
                "Mercado",    # categoria
                "abc",        # valor inválido (tenta novamente sem quebrar)
                "50,25",      # valor válido com vírgula
                "99/99/2026", # data inválida
                "10/11/2026", # data válida
                "0",          # voltar de adicionar
                "3",          # mostrar despesas
                "",           # Enter para voltar
                "2",          # editar despesa
                "1",          # seleciona item 1
                "1",          # alterar
                "Supermercado",
                "75.00",
                "11/11/2026",
                "",           # Enter para voltar da edição
                "3",          # mostrar despesas atualizadas
                "",           # Enter para voltar
                "0",          # sair do usuário
                "0",          # encerrar sistema
            ],
            passwords=[
                "senha123",   # cadastro: senha
                "senha123",   # cadastro: confirmação
                "senha123",   # login: senha
            ],
        )

        joined = "\n".join(outputs)
        self.assertIn("Novo usuário criado com sucesso!", joined)
        self.assertIn("Despesa adicionada com sucesso!", joined)
        self.assertIn("Despesa atualizada com sucesso!", joined)
        self.assertIn("SUPERMERCADO", joined)
        self.assertIn("Despesas totais: R$ 75.00", joined)
        self.assertIn("Dados salvos com sucesso!", joined)

    def test_login_nonexistent_user_can_return_cleanly(self) -> None:
        outputs = self._run_cli(
            inputs=[
                "1",          # login
                "nao_existe", # usuário inexistente
                "0",          # voltar do submenu de erro
                "0",          # encerrar sistema
            ],
            passwords=["qualquer"],
        )
        joined = "\n".join(outputs)
        self.assertIn("Usuário ou senha inválidos.", joined)
        self.assertIn("SISTEMA ENCERRADO.", joined)

    def test_repo_sample_data_is_valid(self) -> None:
        self.assertTrue(storage.authenticate_user("Teste", "2233"))
        expenses = storage.list_expenses("Teste")
        self.assertEqual(len(expenses), 2)
        self.assertEqual(storage.calculate_total(expenses), Decimal("154.00"))


class UIHolstTests(unittest.TestCase):
    """Testes de paleta Holst e alinhamento exato das caixas no CMD."""

    def test_all_holst_palette_colors_present_and_aligned(self) -> None:
        banner = ui.render_brand_banner()
        alert = ui.render_alert("Despesa adicionada com sucesso!", kind="success")
        expenses = [
            storage.Expense("Teste", "Alimentação", Decimal("55.00"), "15/05/2026"),
            storage.Expense("Teste", "Academia", Decimal("99.00"), "21/11/2026"),
        ]
        card = ui.render_card(
            "Total Despesas",
            ui.render_expenses_table(expenses, numbered=True),
            subtitle="Usuário: Teste",
            footer_lines=[ui.style("Despesas totais: R$ 154.00", fg_color=ui.ROSE, bg_color=ui.BG_SLATE)],
        )

        full_output = "\n".join([banner, alert, card])
        for rgb in (ui.BG_DEEP, ui.BG_SLATE, ui.SAGE, ui.TAUPE, ui.ROSE, ui.CREAM):
            code = f"{rgb[0]};{rgb[1]};{rgb[2]}"
            self.assertIn(code, full_output)

        for block in (banner, alert, card):
            for line in block.splitlines():
                self.assertEqual(
                    ui.visible_len(line),
                    ui.CARD_WIDTH,
                    msg=f"Linha desalinhada: {ui.strip_ansi(line)!r}",
                )


class DesktopGUITests(unittest.TestCase):
    """Testes da interface desktop Tkinter (app_gui.py)."""

    def setUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory()
        self.base_dir = Path(self.temp_dir.name)
        self.root = tk.Tk()
        self.root.withdraw()
        self.app = app_gui.ExpenseApp(
            self.root,
            base_dir=self.base_dir,
            confirm_fn=lambda _title, _msg: True,
        )

    def tearDown(self) -> None:
        self.root.destroy()
        self.temp_dir.cleanup()

    def test_holst_palette_constants(self) -> None:
        self.assertEqual(
            (
                app_gui.COLOR_DEEP,
                app_gui.COLOR_SLATE,
                app_gui.COLOR_SAGE,
                app_gui.COLOR_TAUPE,
                app_gui.COLOR_ROSE,
                app_gui.COLOR_CREAM,
            ),
            ("#1E293B", "#334155", "#5C6B66", "#8A7D7B", "#C8A99D", "#F2E6D6"),
        )

    def test_register_login_crud_and_filter_flow(self) -> None:
        # Registra novo usuário pela aba de cadastro
        self.app._switch_auth_tab("register")
        self.app.auth_username.set("carla")
        self.app.auth_password.set("segredo1")
        self.app.auth_confirm.set("segredo1")
        self.app._submit_auth()
        self.assertEqual(self.app.auth_mode.get(), "login")

        # Faz login e abre o painel
        self.app.auth_username.set("carla")
        self.app.auth_password.set("segredo1")
        self.app._submit_auth()
        self.assertEqual(self.app.current_user, "carla")

        # Adiciona duas despesas em meses distintos usando a máscara em tempo real
        self.app.var_amount.set("25")
        self.assertEqual(self.app.var_amount.get(), "R$ 0,25")
        self.app.var_amount.set("2500")
        self.assertEqual(self.app.var_amount.get(), "R$ 25,00")

        self.app.var_category.set("Mercado")
        self.app.var_amount.set("4000")  # R$ 40,00
        self.app.var_date.set("10/11/2026")
        self.app._save_expense()

        self.app.var_category.set("Transporte")
        self.app.var_amount.set("2000")  # R$ 20,00
        self.app.var_date.set("11/10/2026")
        self.app._save_expense()

        # Painel foca no mês atual selecionado (11/2026 -> Total - Novembro)
        self.app.select_current_month("11/2026")
        self.assertEqual(self.app.kpi_period_title_var.get(), "Total - Novembro")
        self.assertEqual(self.app.kpi_total_var.get(), "R$ 40,00")
        # Média mensal: (40 [nov] + 20 [out]) / 2 = R$ 30,00
        self.assertEqual(self.app.kpi_monthly_avg_var.get(), "R$ 30,00")

        # Configura salário de R$ 35,00 (gasto em nov 40,00 > 35,00 => devendo 5,00)
        self.app.var_salary.set("3500")
        self.assertEqual(self.app.var_salary.get(), "R$ 35,00")
        self.app._save_salary()
        self.assertEqual(self.app.kpi_available_var.get(), "R$ 0,00")
        self.assertEqual(self.app.kpi_debt_var.get(), "R$ 5,00")

        # Troca o mês atual para Outubro/2026 e edita a despesa preservando o índice real
        self.app.select_current_month("10/2026")
        self.assertEqual(self.app.kpi_period_title_var.get(), "Total - Outubro")
        self.assertEqual(self.app.kpi_total_var.get(), "R$ 20,00")
        self.assertEqual(self.app.kpi_available_var.get(), "R$ 15,00")
        self.assertEqual(self.app.kpi_debt_var.get(), "R$ 0,00")

        self.root.update_idletasks()
        children = self.app.tree.get_children()
        self.assertEqual(children, ("1",))

        self.app.tree.selection_set("1")
        self.app._on_tree_select(None)
        self.assertEqual(self.app.selected_expense_index, 1)

        self.app.var_category.set("Metrô")
        self.app.var_amount.set("2500")  # R$ 25,00
        self.app.var_date.set("12/10/2026")
        self.app._save_expense()

        self.assertEqual(self.app.kpi_total_var.get(), "R$ 25,00")
        self.assertEqual(self.app.kpi_monthly_avg_var.get(), "R$ 32,50")

        # Abre a tela de Resumo Anual / Por Mês
        self.app.show_annual_summary("carla")
        self.assertEqual(self.app.annual_total_var.get(), "R$ 65,00")
        self.assertEqual(self.app.annual_monthly_avg_var.get(), "R$ 32,50")
        self.assertEqual(len(self.app.summary_month_tree.get_children()), 12)

        self.app.select_summary_month(10, 2026)
        self.assertEqual(self.app.summary_month_title_var.get(), "Total - Outubro")
        self.assertEqual(self.app.summary_month_total_var.get(), "R$ 25,00")
        self.assertEqual(len(self.app.detail_tree.get_children()), 1)

        # Volta ao painel e exclui o lançamento de Outubro
        self.app.show_dashboard("carla")
        self.app.select_current_month("10/2026")
        self.app.tree.selection_set("1")
        self.app._on_tree_select(None)
        self.app._delete_selected()

        self.assertEqual(self.app.kpi_total_var.get(), "R$ 0,00")
        self.assertEqual(self.app.kpi_available_var.get(), "R$ 35,00")
        self.assertEqual(self.app.kpi_debt_var.get(), "R$ 0,00")

    def test_remember_login_auto_opens_dashboard_and_logout_clears(self) -> None:
        storage.register_user("diego", "1234", self.base_dir)
        self.app.auth_username.set("diego")
        self.app.auth_password.set("1234")
        self.app.auth_remember_me.set(True)
        self.app._submit_auth()
        self.assertEqual(self.app.current_user, "diego")

        # Simula reabrir o aplicativo em uma nova janela
        root2 = tk.Tk()
        root2.withdraw()
        try:
            app2 = app_gui.ExpenseApp(root2, base_dir=self.base_dir)
            self.assertEqual(app2.current_user, "diego")

            # Sair da conta limpa o login salvo
            app2._logout()
            self.assertIsNone(app2.current_user)
            self.assertIsNone(storage.load_saved_session(self.base_dir))
        finally:
            root2.destroy()


if __name__ == "__main__":
    unittest.main()
