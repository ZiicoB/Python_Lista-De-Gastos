"""Interface gráfica desktop (Tkinter) do sistema Lista de Gastos — Paleta Holst."""

from __future__ import annotations

import os
import tkinter as tk
from datetime import date
from decimal import Decimal
from pathlib import Path
from tkinter import ttk
from typing import Callable

import storage

# Paleta oficial "Holst"
COLOR_DEEP = "#1E293B"
COLOR_SLATE = "#334155"
COLOR_SAGE = "#5C6B66"
COLOR_TAUPE = "#8A7D7B"
COLOR_ROSE = "#C8A99D"
COLOR_CREAM = "#F2E6D6"
COLOR_ROW_ALT = "#253347"

FONT_FAMILY = "Segoe UI"
FONT_MONO = "Consolas"


def _enable_windows_dpi_and_dark_titlebar(root: tk.Tk) -> None:
    """Ativa nitidez High-DPI e barra de título escura no Windows 10/11."""
    if os.name != "nt":
        return
    try:
        import ctypes

        ctypes.windll.shcore.SetProcessDpiAwareness(1)  # type: ignore[attr-defined]
    except Exception:
        pass
    try:
        import ctypes

        root.update_idletasks()
        hwnd = ctypes.windll.user32.GetParent(root.winfo_id())  # type: ignore[attr-defined]
        dark = ctypes.c_int(1)
        for attr in (20, 19):
            ctypes.windll.dwmapi.DwmSetWindowAttribute(  # type: ignore[attr-defined]
                hwnd, attr, ctypes.byref(dark), ctypes.sizeof(dark)
            )
    except Exception:
        pass


def _style_button(
    parent: tk.Widget,
    text: str,
    command: Callable[[], None],
    *,
    bg: str = COLOR_ROSE,
    fg: str = COLOR_DEEP,
    hover_bg: str = COLOR_CREAM,
    hover_fg: str = COLOR_DEEP,
    font_size: int = 10,
    bold: bool = True,
    padx: int = 14,
    pady: int = 8,
) -> tk.Button:
    """Cria botão plano estilizado com efeito hover na paleta Holst."""
    weight = "bold" if bold else "normal"
    btn = tk.Button(
        parent,
        text=text,
        command=command,
        bg=bg,
        fg=fg,
        activebackground=hover_bg,
        activeforeground=hover_fg,
        relief="flat",
        bd=0,
        highlightthickness=0,
        cursor="hand2",
        font=(FONT_FAMILY, font_size, weight),
        padx=padx,
        pady=pady,
    )
    btn.bind("<Enter>", lambda _e: btn.configure(bg=hover_bg, fg=hover_fg))
    btn.bind("<Leave>", lambda _e: btn.configure(bg=bg, fg=fg))
    return btn


def _style_entry(
    parent: tk.Widget,
    textvariable: tk.StringVar,
    *,
    show: str = "",
) -> tk.Entry:
    """Cria campo de texto escuro com borda sutil em taupe e foco em rosé."""
    return tk.Entry(
        parent,
        textvariable=textvariable,
        show=show,
        bg=COLOR_DEEP,
        fg=COLOR_CREAM,
        insertbackground=COLOR_ROSE,
        selectbackground=COLOR_SAGE,
        selectforeground=COLOR_CREAM,
        relief="flat",
        bd=0,
        highlightthickness=1,
        highlightbackground=COLOR_TAUPE,
        highlightcolor=COLOR_ROSE,
        font=(FONT_FAMILY, 10),
    )


def _attach_currency_mask(var: tk.StringVar, entry: tk.Entry) -> None:
    """Aplica máscara em tempo real estilo moeda BRL (25 -> R$ 0,25)."""
    state: dict[str, object] = {"updating": False, "after_id": None}

    def _safe_cursor_end() -> None:
        state["after_id"] = None
        try:
            if entry.winfo_exists():
                entry.icursor(tk.END)
        except tk.TclError:
            pass

    def _schedule_cursor_end(_event: object = None) -> None:
        try:
            if not entry.winfo_exists():
                return
            pending = state["after_id"]
            if pending is not None:
                entry.after_cancel(str(pending))
            state["after_id"] = entry.after_idle(_safe_cursor_end)
        except tk.TclError:
            pass

    def _cancel_pending(_event: object = None) -> None:
        pending = state["after_id"]
        if pending is not None:
            try:
                entry.after_cancel(str(pending))
            except tk.TclError:
                pass
            state["after_id"] = None

    def _on_write(*_args: object) -> None:
        if state["updating"]:
            return
        state["updating"] = True
        try:
            formatted = storage.format_currency_from_digits(var.get())
            if var.get() != formatted:
                var.set(formatted)
            _schedule_cursor_end()
        finally:
            state["updating"] = False

    var.trace_add("write", _on_write)
    entry.bind("<FocusIn>", _schedule_cursor_end)
    entry.bind("<ButtonRelease-1>", _schedule_cursor_end)
    entry.bind("<KeyRelease>", _schedule_cursor_end)
    entry.bind("<Destroy>", _cancel_pending)

    if not var.get():
        var.set("R$ 0,00")


def _center_window(win: tk.Tk | tk.Toplevel, width: int, height: int) -> None:
    win.update_idletasks()
    screen_w = win.winfo_screenwidth()
    screen_h = win.winfo_screenheight()
    pos_x = max(0, (screen_w - width) // 2)
    pos_y = max(0, (screen_h - height) // 2)
    win.geometry(f"{width}x{height}+{pos_x}+{pos_y}")


class ExpenseApp:
    """Aplicativo desktop principal para gerenciamento de despesas."""

    def __init__(
        self,
        root: tk.Tk,
        *,
        base_dir: Path = storage.BASE_DIR,
        confirm_fn: Callable[[str, str], bool] | None = None,
    ) -> None:
        self.root = root
        self.base_dir = base_dir
        self.confirm_fn = confirm_fn or self._modal_confirm

        self.current_user: str | None = None
        self.selected_expense_index: int | None = None
        self.active_month_key: str = date.today().strftime("%m/%Y")
        self._all_expenses: list[storage.Expense] = []
        self._month_label_to_key: dict[str, str] = {}

        self.root.title("Lista de Gastos — Controle Financeiro")
        self.root.configure(bg=COLOR_DEEP)
        self.root.minsize(940, 660)
        _center_window(self.root, 1140, 750)

        self._configure_ttk_theme()

        self.container = tk.Frame(self.root, bg=COLOR_DEEP)
        self.container.pack(fill="both", expand=True)

        saved_user = storage.load_saved_session(self.base_dir)
        if saved_user:
            self.show_dashboard(saved_user)
        else:
            self.show_auth_screen()

    def _configure_ttk_theme(self) -> None:
        style = ttk.Style(self.root)
        style.theme_use("clam")

        style.configure(
            "Holst.Treeview",
            background=COLOR_DEEP,
            fieldbackground=COLOR_DEEP,
            foreground=COLOR_CREAM,
            rowheight=32,
            borderwidth=0,
            relief="flat",
            font=(FONT_FAMILY, 10),
        )
        style.map(
            "Holst.Treeview",
            background=[("selected", COLOR_SAGE)],
            foreground=[("selected", COLOR_CREAM)],
        )
        style.configure(
            "Holst.Treeview.Heading",
            background=COLOR_SLATE,
            foreground=COLOR_ROSE,
            relief="flat",
            borderwidth=0,
            padding=(10, 8),
            font=(FONT_FAMILY, 10, "bold"),
        )
        style.map(
            "Holst.Treeview.Heading",
            background=[("active", COLOR_TAUPE)],
            foreground=[("active", COLOR_CREAM)],
        )
        style.configure(
            "Holst.Vertical.TScrollbar",
            background=COLOR_SLATE,
            troughcolor=COLOR_DEEP,
            bordercolor=COLOR_DEEP,
            arrowcolor=COLOR_ROSE,
            relief="flat",
        )
        style.configure(
            "Holst.TCombobox",
            fieldbackground=COLOR_DEEP,
            background=COLOR_SLATE,
            foreground=COLOR_CREAM,
            arrowcolor=COLOR_ROSE,
            bordercolor=COLOR_TAUPE,
            lightcolor=COLOR_TAUPE,
            darkcolor=COLOR_TAUPE,
            padding=5,
        )
        style.map(
            "Holst.TCombobox",
            fieldbackground=[("readonly", COLOR_DEEP)],
            foreground=[("readonly", COLOR_CREAM)],
            selectbackground=[("readonly", COLOR_SAGE)],
            selectforeground=[("readonly", COLOR_CREAM)],
        )

    def _clear_container(self) -> None:
        for child in self.container.winfo_children():
            child.destroy()

    def _modal_confirm(self, title: str, message: str) -> bool:
        """Exibe caixa de confirmação estilizada na paleta Holst."""
        result = {"confirmed": False}
        dialog = tk.Toplevel(self.root)
        dialog.title(title)
        dialog.configure(bg=COLOR_SLATE)
        dialog.resizable(False, False)
        dialog.transient(self.root)
        dialog.grab_set()

        frame = tk.Frame(
            dialog,
            bg=COLOR_SLATE,
            padx=24,
            pady=20,
            highlightthickness=1,
            highlightbackground=COLOR_TAUPE,
        )
        frame.pack(fill="both", expand=True)

        tk.Label(
            frame,
            text=title,
            bg=COLOR_SLATE,
            fg=COLOR_ROSE,
            font=(FONT_FAMILY, 12, "bold"),
            anchor="w",
        ).pack(fill="x")

        tk.Label(
            frame,
            text=message,
            bg=COLOR_SLATE,
            fg=COLOR_CREAM,
            font=(FONT_FAMILY, 10),
            wraplength=340,
            justify="left",
            anchor="w",
        ).pack(fill="x", pady=(10, 18))

        btn_row = tk.Frame(frame, bg=COLOR_SLATE)
        btn_row.pack(fill="x")

        def confirm() -> None:
            result["confirmed"] = True
            dialog.destroy()

        def cancel() -> None:
            dialog.destroy()

        _style_button(
            btn_row,
            "Excluir",
            confirm,
            bg=COLOR_ROSE,
            fg=COLOR_DEEP,
            hover_bg=COLOR_CREAM,
        ).pack(side="right", padx=(8, 0))
        _style_button(
            btn_row,
            "Cancelar",
            cancel,
            bg=COLOR_DEEP,
            fg=COLOR_CREAM,
            hover_bg=COLOR_TAUPE,
            hover_fg=COLOR_CREAM,
            bold=False,
        ).pack(side="right")

        _center_window(dialog, 390, 175)
        dialog.wait_window()
        return result["confirmed"]

    # ------------------------------------------------------------------
    # Tela de Autenticação (Login / Cadastro)
    # ------------------------------------------------------------------
    def show_auth_screen(self, *, default_tab: str = "login", notice: str = "") -> None:
        self._clear_container()
        self.current_user = None
        self.selected_expense_index = None

        wrapper = tk.Frame(self.container, bg=COLOR_DEEP)
        wrapper.place(relx=0.5, rely=0.5, anchor="center")

        card = tk.Frame(
            wrapper,
            bg=COLOR_SLATE,
            padx=34,
            pady=28,
            highlightthickness=1,
            highlightbackground=COLOR_TAUPE,
        )
        card.pack()

        swatch_bar = tk.Frame(card, bg=COLOR_SLATE)
        swatch_bar.pack(fill="x", pady=(0, 16))
        for color in (COLOR_DEEP, COLOR_SLATE, COLOR_SAGE, COLOR_TAUPE, COLOR_ROSE, COLOR_CREAM):
            tk.Frame(swatch_bar, bg=color, height=6, width=54).pack(side="left", expand=True, fill="x")

        tk.Label(
            card,
            text="✦  LISTA DE GASTOS",
            bg=COLOR_SLATE,
            fg=COLOR_ROSE,
            font=(FONT_FAMILY, 18, "bold"),
        ).pack(anchor="w")

        tk.Label(
            card,
            text="Controle financeiro pessoal",
            bg=COLOR_SLATE,
            fg=COLOR_CREAM,
            font=(FONT_FAMILY, 10),
        ).pack(anchor="w", pady=(2, 18))

        tab_bar = tk.Frame(card, bg=COLOR_DEEP, padx=4, pady=4)
        tab_bar.pack(fill="x", pady=(0, 16))

        self.auth_mode = tk.StringVar(value=default_tab)
        self.auth_username = tk.StringVar()
        self.auth_password = tk.StringVar()
        self.auth_confirm = tk.StringVar()
        self.auth_show_pass = tk.BooleanVar(value=False)
        self.auth_remember_me = tk.BooleanVar(value=False)

        self.auth_status_label = tk.Label(
            card,
            text=notice,
            bg=COLOR_SLATE,
            fg=COLOR_CREAM if notice else COLOR_ROSE,
            font=(FONT_FAMILY, 9, "bold"),
            wraplength=340,
            justify="left",
            anchor="w",
        )

        self.btn_tab_login = tk.Button(
            tab_bar,
            text="Entrar",
            relief="flat",
            bd=0,
            cursor="hand2",
            font=(FONT_FAMILY, 10, "bold"),
            pady=7,
            command=lambda: self._switch_auth_tab("login"),
        )
        self.btn_tab_login.pack(side="left", fill="x", expand=True)

        self.btn_tab_register = tk.Button(
            tab_bar,
            text="Criar Conta",
            relief="flat",
            bd=0,
            cursor="hand2",
            font=(FONT_FAMILY, 10, "bold"),
            pady=7,
            command=lambda: self._switch_auth_tab("register"),
        )
        self.btn_tab_register.pack(side="left", fill="x", expand=True)

        form = tk.Frame(card, bg=COLOR_SLATE, width=340)
        form.pack(fill="x")

        tk.Label(
            form,
            text="Usuário",
            bg=COLOR_SLATE,
            fg=COLOR_CREAM,
            font=(FONT_FAMILY, 9, "bold"),
        ).pack(anchor="w", pady=(0, 4))
        self.entry_auth_user = _style_entry(form, self.auth_username)
        self.entry_auth_user.pack(fill="x", ipady=7, pady=(0, 12))

        tk.Label(
            form,
            text="Senha",
            bg=COLOR_SLATE,
            fg=COLOR_CREAM,
            font=(FONT_FAMILY, 9, "bold"),
        ).pack(anchor="w", pady=(0, 4))
        self.entry_auth_pass = _style_entry(form, self.auth_password, show="•")
        self.entry_auth_pass.pack(fill="x", ipady=7, pady=(0, 8))

        self.confirm_frame = tk.Frame(form, bg=COLOR_SLATE)
        tk.Label(
            self.confirm_frame,
            text="Confirmar Senha",
            bg=COLOR_SLATE,
            fg=COLOR_CREAM,
            font=(FONT_FAMILY, 9, "bold"),
        ).pack(anchor="w", pady=(4, 4))
        self.entry_auth_confirm = _style_entry(self.confirm_frame, self.auth_confirm, show="•")
        self.entry_auth_confirm.pack(fill="x", ipady=7, pady=(0, 8))

        options_row = tk.Frame(form, bg=COLOR_SLATE)
        options_row.pack(fill="x", pady=(0, 8))

        tk.Checkbutton(
            options_row,
            text="Mostrar senha",
            variable=self.auth_show_pass,
            command=self._toggle_password_visibility,
            bg=COLOR_SLATE,
            fg=COLOR_TAUPE,
            activebackground=COLOR_SLATE,
            activeforeground=COLOR_CREAM,
            selectcolor=COLOR_DEEP,
            highlightthickness=0,
            bd=0,
            cursor="hand2",
            font=(FONT_FAMILY, 9),
        ).pack(side="left")

        self.chk_remember_me = tk.Checkbutton(
            options_row,
            text="Salvar login",
            variable=self.auth_remember_me,
            bg=COLOR_SLATE,
            fg=COLOR_CREAM,
            activebackground=COLOR_SLATE,
            activeforeground=COLOR_ROSE,
            selectcolor=COLOR_DEEP,
            highlightthickness=0,
            bd=0,
            cursor="hand2",
            font=(FONT_FAMILY, 9),
        )
        self.chk_remember_me.pack(side="right")

        self.auth_status_label.pack(fill="x", pady=(0, 10))

        self.auth_submit_holder = tk.Frame(card, bg=COLOR_SLATE)
        self.auth_submit_holder.pack(fill="x")

        self.entry_auth_user.bind("<Return>", lambda _e: self._submit_auth())
        self.entry_auth_pass.bind("<Return>", lambda _e: self._submit_auth())
        self.entry_auth_confirm.bind("<Return>", lambda _e: self._submit_auth())

        self._switch_auth_tab(default_tab, preserve_notice=bool(notice))
        self.entry_auth_user.focus_set()

    def _toggle_password_visibility(self) -> None:
        mask = "" if self.auth_show_pass.get() else "•"
        self.entry_auth_pass.configure(show=mask)
        self.entry_auth_confirm.configure(show=mask)

    def _switch_auth_tab(self, mode: str, *, preserve_notice: bool = False) -> None:
        self.auth_mode.set(mode)
        if not preserve_notice:
            self.auth_status_label.configure(text="")

        for child in self.auth_submit_holder.winfo_children():
            child.destroy()

        if mode == "login":
            self.btn_tab_login.configure(bg=COLOR_ROSE, fg=COLOR_DEEP)
            self.btn_tab_register.configure(bg=COLOR_DEEP, fg=COLOR_TAUPE)
            self.confirm_frame.pack_forget()
            self.chk_remember_me.pack(side="right")
            _style_button(
                self.auth_submit_holder,
                "Entrar na Conta",
                self._submit_auth,
                bg=COLOR_ROSE,
                fg=COLOR_DEEP,
                hover_bg=COLOR_CREAM,
                pady=10,
            ).pack(fill="x")
        else:
            self.btn_tab_login.configure(bg=COLOR_DEEP, fg=COLOR_TAUPE)
            self.btn_tab_register.configure(bg=COLOR_SAGE, fg=COLOR_CREAM)
            self.confirm_frame.pack(fill="x", pady=(0, 4))
            self.chk_remember_me.pack_forget()
            _style_button(
                self.auth_submit_holder,
                "Criar Nova Conta",
                self._submit_auth,
                bg=COLOR_SAGE,
                fg=COLOR_CREAM,
                hover_bg=COLOR_ROSE,
                hover_fg=COLOR_DEEP,
                pady=10,
            ).pack(fill="x")

    def _set_auth_feedback(self, message: str, *, success: bool = False) -> None:
        color = COLOR_CREAM if success else COLOR_ROSE
        self.auth_status_label.configure(text=message, fg=color)

    def _submit_auth(self) -> None:
        username = self.auth_username.get().strip()
        password = self.auth_password.get()

        if self.auth_mode.get() == "login":
            if not username or not password:
                self._set_auth_feedback("Informe usuário e senha.")
                return
            if storage.authenticate_user(username, password, self.base_dir):
                if self.auth_remember_me.get():
                    storage.save_session(username, self.base_dir)
                else:
                    storage.clear_saved_session(self.base_dir)
                self.show_dashboard(username)
                return
            self._set_auth_feedback("Usuário ou senha inválidos.")
            return

        confirm = self.auth_confirm.get()
        if password != confirm:
            self._set_auth_feedback("As senhas não coincidem.")
            return
        try:
            created_user = storage.register_user(username, password, self.base_dir)
        except storage.ValidationError as exc:
            self._set_auth_feedback(str(exc))
            return

        self.auth_password.set("")
        self.auth_confirm.set("")
        self._switch_auth_tab("login", preserve_notice=True)
        self._set_auth_feedback(
            f"Conta '{created_user}' criada com sucesso! Faça login.",
            success=True,
        )

    # ------------------------------------------------------------------
    # Barra superior compartilhada e helpers
    # ------------------------------------------------------------------
    def _build_top_bar(
        self,
        username: str,
        *,
        nav_button_text: str,
        nav_command: Callable[[], None],
        subtitle_badge: str = "",
    ) -> None:
        header = tk.Frame(
            self.container,
            bg=COLOR_SLATE,
            padx=24,
            pady=12,
            highlightthickness=1,
            highlightbackground=COLOR_TAUPE,
        )
        header.pack(fill="x")

        left_hdr = tk.Frame(header, bg=COLOR_SLATE)
        left_hdr.pack(side="left")

        tk.Label(
            left_hdr,
            text="✦  LISTA DE GASTOS",
            bg=COLOR_SLATE,
            fg=COLOR_ROSE,
            font=(FONT_FAMILY, 14, "bold"),
        ).pack(side="left")

        tk.Label(
            left_hdr,
            text=f"  ●  {username}  ",
            bg=COLOR_SAGE,
            fg=COLOR_CREAM,
            font=(FONT_FAMILY, 9, "bold"),
            padx=8,
            pady=3,
        ).pack(side="left", padx=(14, 0))

        if subtitle_badge:
            tk.Label(
                left_hdr,
                text=subtitle_badge,
                bg=COLOR_SLATE,
                fg=COLOR_TAUPE,
                font=(FONT_FAMILY, 9, "bold"),
            ).pack(side="left", padx=(12, 0))

        right_hdr = tk.Frame(header, bg=COLOR_SLATE)
        right_hdr.pack(side="right")

        _style_button(
            right_hdr,
            nav_button_text,
            nav_command,
            bg=COLOR_ROSE,
            fg=COLOR_DEEP,
            hover_bg=COLOR_CREAM,
            font_size=9,
            padx=12,
            pady=6,
        ).pack(side="left", padx=(0, 10))

        _style_button(
            right_hdr,
            "Sair da Conta",
            self._logout,
            bg=COLOR_DEEP,
            fg=COLOR_ROSE,
            hover_bg=COLOR_TAUPE,
            hover_fg=COLOR_CREAM,
            font_size=9,
            padx=12,
            pady=6,
        ).pack(side="left")

    def _logout(self) -> None:
        storage.clear_saved_session(self.base_dir)
        self.show_auth_screen(notice="Sessão encerrada com segurança.")

    def _build_kpi_card(
        self,
        parent: tk.Frame,
        column: int,
        title: str | tk.StringVar,
        value_var: tk.StringVar,
        value_color: str,
        *,
        total_columns: int = 4,
    ) -> tk.Label:
        pad = (0, 10) if column < total_columns - 1 else (0, 0)
        card = tk.Frame(
            parent,
            bg=COLOR_SLATE,
            padx=16,
            pady=12,
            highlightthickness=1,
            highlightbackground=COLOR_TAUPE,
        )
        card.grid(row=0, column=column, sticky="ew", padx=pad)

        title_kwargs: dict[str, object] = {
            "bg": COLOR_SLATE,
            "fg": COLOR_TAUPE,
            "font": (FONT_FAMILY, 8, "bold"),
            "anchor": "w",
        }
        if isinstance(title, tk.StringVar):
            title_kwargs["textvariable"] = title
        else:
            title_kwargs["text"] = title
        tk.Label(card, **title_kwargs).pack(fill="x")

        value_lbl = tk.Label(
            card,
            textvariable=value_var,
            bg=COLOR_SLATE,
            fg=value_color,
            font=(FONT_MONO, 14, "bold"),
            anchor="w",
        )
        value_lbl.pack(fill="x", pady=(4, 0))
        return value_lbl

    # ------------------------------------------------------------------
    # Painel Principal (Mês Atual + Salário + Gastos do Mês)
    # ------------------------------------------------------------------
    def show_dashboard(self, username: str) -> None:
        self._clear_container()
        self.current_user = username
        self.selected_expense_index = None
        storage.get_user_expense_file(username, self.base_dir)

        self._build_top_bar(
            username,
            nav_button_text="Resumo Anual / Por Mês",
            nav_command=lambda: self.show_annual_summary(username),
        )

        main_area = tk.Frame(self.container, bg=COLOR_DEEP, padx=22, pady=14)
        main_area.pack(fill="both", expand=True)

        # Barra de Mês Atual + Salário Mensal & Comparativo
        top_controls_card = tk.Frame(
            main_area,
            bg=COLOR_SLATE,
            padx=18,
            pady=12,
            highlightthickness=1,
            highlightbackground=COLOR_TAUPE,
        )
        top_controls_card.pack(fill="x", pady=(0, 12))

        left_ctrl = tk.Frame(top_controls_card, bg=COLOR_SLATE)
        left_ctrl.pack(side="left")

        tk.Label(
            left_ctrl,
            text="Mês atual:",
            bg=COLOR_SLATE,
            fg=COLOR_ROSE,
            font=(FONT_FAMILY, 10, "bold"),
        ).pack(side="left", padx=(0, 8))

        self.var_current_month = tk.StringVar(
            value=storage.format_month_full_label(self.active_month_key)
        )
        self.combo_current_month = ttk.Combobox(
            left_ctrl,
            textvariable=self.var_current_month,
            values=[storage.format_month_full_label(self.active_month_key)],
            state="readonly",
            width=18,
            style="Holst.TCombobox",
        )
        self.combo_current_month.pack(side="left", padx=(0, 18))
        self.combo_current_month.bind(
            "<<ComboboxSelected>>", lambda _e: self._on_current_month_selected()
        )

        tk.Label(
            left_ctrl,
            text="Salário Mensal:",
            bg=COLOR_SLATE,
            fg=COLOR_CREAM,
            font=(FONT_FAMILY, 10, "bold"),
        ).pack(side="left", padx=(0, 8))

        saved_salary = storage.get_user_salary(username, self.base_dir)
        self.var_salary = tk.StringVar(value=storage.format_brl(saved_salary))
        self.entry_salary = _style_entry(left_ctrl, self.var_salary)
        self.entry_salary.configure(width=16)
        self.entry_salary.pack(side="left", ipady=5, padx=(0, 8))
        _attach_currency_mask(self.var_salary, self.entry_salary)
        self.entry_salary.bind("<Return>", lambda _e: self._save_salary())

        _style_button(
            left_ctrl,
            "Salvar Salário",
            self._save_salary,
            bg=COLOR_SAGE,
            fg=COLOR_CREAM,
            hover_bg=COLOR_ROSE,
            hover_fg=COLOR_DEEP,
            font_size=9,
            padx=12,
            pady=5,
        ).pack(side="left")

        right_ctrl = tk.Frame(top_controls_card, bg=COLOR_SLATE)
        right_ctrl.pack(side="right", fill="x", expand=True, padx=(20, 0))

        self.budget_status_var = tk.StringVar(
            value="Defina seu salário mensal para comparar os gastos."
        )
        tk.Label(
            right_ctrl,
            textvariable=self.budget_status_var,
            bg=COLOR_SLATE,
            fg=COLOR_CREAM,
            font=(FONT_FAMILY, 9, "bold"),
            anchor="e",
        ).pack(fill="x", pady=(0, 5))

        self.budget_bar = tk.Canvas(
            right_ctrl,
            height=12,
            bg=COLOR_DEEP,
            highlightthickness=1,
            highlightbackground=COLOR_TAUPE,
        )
        self.budget_bar.pack(fill="x")
        self.budget_bar.bind("<Configure>", lambda _e: self._draw_budget_bar())

        self._budget_ratio = 0.0
        self._budget_over = False

        # 4 Cartões KPI
        kpi_row = tk.Frame(main_area, bg=COLOR_DEEP)
        kpi_row.pack(fill="x", pady=(0, 12))
        for col in range(4):
            kpi_row.columnconfigure(col, weight=1, uniform="kpi")

        self.kpi_period_title_var = tk.StringVar(
            value=f"Total - {storage.get_month_name(self.active_month_key)}"
        )
        self.kpi_total_var = tk.StringVar(value="R$ 0,00")
        self.kpi_monthly_avg_var = tk.StringVar(value="R$ 0,00")
        self.kpi_available_var = tk.StringVar(value="R$ 0,00")
        self.kpi_debt_var = tk.StringVar(value="R$ 0,00")

        self._build_kpi_card(kpi_row, 0, self.kpi_period_title_var, self.kpi_total_var, COLOR_CREAM)
        self._build_kpi_card(kpi_row, 1, "MÉDIA DE GASTO MENSAL", self.kpi_monthly_avg_var, COLOR_CREAM)
        self.lbl_available_val = self._build_kpi_card(
            kpi_row, 2, "DISPONÍVEL NO MÊS", self.kpi_available_var, COLOR_CREAM
        )
        self.lbl_debt_val = self._build_kpi_card(
            kpi_row, 3, "VAI FICAR DEVENDO", self.kpi_debt_var, COLOR_ROSE
        )

        # Conteúdo dividido: Formulário (esquerda) + Tabela do Mês (direita)
        content = tk.Frame(main_area, bg=COLOR_DEEP)
        content.pack(fill="both", expand=True)
        content.columnconfigure(0, weight=0)
        content.columnconfigure(1, weight=1)
        content.rowconfigure(0, weight=1)

        # Painel esquerdo (Formulário)
        form_card = tk.Frame(
            content,
            bg=COLOR_SLATE,
            width=310,
            padx=20,
            pady=16,
            highlightthickness=1,
            highlightbackground=COLOR_TAUPE,
        )
        form_card.grid(row=0, column=0, sticky="nsew", padx=(0, 16))
        form_card.grid_propagate(False)

        self.form_title_var = tk.StringVar(value="Nova Despesa")
        tk.Label(
            form_card,
            textvariable=self.form_title_var,
            bg=COLOR_SLATE,
            fg=COLOR_ROSE,
            font=(FONT_FAMILY, 13, "bold"),
            anchor="w",
        ).pack(fill="x", pady=(0, 10))

        self.var_category = tk.StringVar()
        self.var_amount = tk.StringVar(value="R$ 0,00")
        self.var_date = tk.StringVar(
            value=storage.default_date_for_month(self.active_month_key)
        )

        tk.Label(
            form_card,
            text="Categoria",
            bg=COLOR_SLATE,
            fg=COLOR_CREAM,
            font=(FONT_FAMILY, 9, "bold"),
        ).pack(anchor="w", pady=(0, 4))
        self.entry_category = _style_entry(form_card, self.var_category)
        self.entry_category.pack(fill="x", ipady=7, pady=(0, 10))

        tk.Label(
            form_card,
            text="Valor",
            bg=COLOR_SLATE,
            fg=COLOR_CREAM,
            font=(FONT_FAMILY, 9, "bold"),
        ).pack(anchor="w", pady=(0, 4))
        self.entry_amount = _style_entry(form_card, self.var_amount)
        self.entry_amount.pack(fill="x", ipady=7, pady=(0, 10))
        _attach_currency_mask(self.var_amount, self.entry_amount)

        date_lbl_row = tk.Frame(form_card, bg=COLOR_SLATE)
        date_lbl_row.pack(fill="x", pady=(0, 4))
        tk.Label(
            date_lbl_row,
            text="Data (DD/MM/AAAA)",
            bg=COLOR_SLATE,
            fg=COLOR_CREAM,
            font=(FONT_FAMILY, 9, "bold"),
        ).pack(side="left")
        self.btn_today = _style_button(
            date_lbl_row,
            "Hoje",
            lambda: self.var_date.set(date.today().strftime("%d/%m/%Y")),
            bg=COLOR_DEEP,
            fg=COLOR_ROSE,
            hover_bg=COLOR_TAUPE,
            hover_fg=COLOR_CREAM,
            font_size=8,
            padx=8,
            pady=2,
        )
        self.btn_today.pack(side="right")

        self.entry_date = _style_entry(form_card, self.var_date)
        self.entry_date.pack(fill="x", ipady=7, pady=(0, 10))

        self.form_feedback = tk.Label(
            form_card,
            text="",
            bg=COLOR_SLATE,
            fg=COLOR_ROSE,
            font=(FONT_FAMILY, 9, "bold"),
            wraplength=265,
            justify="left",
            anchor="w",
        )
        self.form_feedback.pack(fill="x", pady=(0, 10))

        self.form_buttons_holder = tk.Frame(form_card, bg=COLOR_SLATE)
        self.form_buttons_holder.pack(fill="x")
        self._render_form_buttons()

        self.entry_category.bind("<Return>", lambda _e: self._save_expense())
        self.entry_amount.bind("<Return>", lambda _e: self._save_expense())
        self.entry_date.bind("<Return>", lambda _e: self._save_expense())

        # Painel direito (Tabela do Mês Atual + Busca)
        table_card = tk.Frame(
            content,
            bg=COLOR_SLATE,
            padx=20,
            pady=16,
            highlightthickness=1,
            highlightbackground=COLOR_TAUPE,
        )
        table_card.grid(row=0, column=1, sticky="nsew")

        top_table_bar = tk.Frame(table_card, bg=COLOR_SLATE)
        top_table_bar.pack(fill="x", pady=(0, 12))

        self.table_title_var = tk.StringVar(
            value=f"Despesas de {storage.format_month_full_label(self.active_month_key)}"
        )
        tk.Label(
            top_table_bar,
            textvariable=self.table_title_var,
            bg=COLOR_SLATE,
            fg=COLOR_ROSE,
            font=(FONT_FAMILY, 13, "bold"),
        ).pack(side="left")

        search_box = tk.Frame(top_table_bar, bg=COLOR_SLATE)
        search_box.pack(side="right")
        tk.Label(
            search_box,
            text="Buscar:",
            bg=COLOR_SLATE,
            fg=COLOR_TAUPE,
            font=(FONT_FAMILY, 9, "bold"),
        ).pack(side="left", padx=(0, 6))
        self.var_search = tk.StringVar()
        self.var_search.trace_add("write", lambda *_args: self._refresh_table())
        self.entry_search = _style_entry(search_box, self.var_search)
        self.entry_search.configure(width=20)
        self.entry_search.pack(side="left", ipady=4)

        tree_frame = tk.Frame(table_card, bg=COLOR_DEEP)
        tree_frame.pack(fill="both", expand=True)

        columns = ("num", "category", "amount", "date")
        self.tree = ttk.Treeview(
            tree_frame,
            columns=columns,
            show="headings",
            style="Holst.Treeview",
            selectmode="browse",
        )
        self.tree.heading("num", text="#", anchor="center")
        self.tree.heading("category", text="Categoria", anchor="w")
        self.tree.heading("amount", text="Valor (R$)", anchor="e")
        self.tree.heading("date", text="Data", anchor="center")

        self.tree.column("num", width=48, minwidth=36, stretch=False, anchor="center")
        self.tree.column("category", width=280, minwidth=140, stretch=True, anchor="w")
        self.tree.column("amount", width=135, minwidth=100, stretch=False, anchor="e")
        self.tree.column("date", width=115, minwidth=95, stretch=False, anchor="center")

        self.tree.tag_configure("even", background=COLOR_DEEP, foreground=COLOR_CREAM)
        self.tree.tag_configure("odd", background=COLOR_ROW_ALT, foreground=COLOR_CREAM)

        scrollbar = ttk.Scrollbar(
            tree_frame,
            orient="vertical",
            command=self.tree.yview,
            style="Holst.Vertical.TScrollbar",
        )
        self.tree.configure(yscrollcommand=scrollbar.set)

        self.tree.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")

        self.tree.bind("<<TreeviewSelect>>", self._on_tree_select)

        self.table_footer_var = tk.StringVar(value="")
        tk.Label(
            table_card,
            textvariable=self.table_footer_var,
            bg=COLOR_SLATE,
            fg=COLOR_TAUPE,
            font=(FONT_FAMILY, 9),
            anchor="w",
        ).pack(fill="x", pady=(10, 0))

        self.reload_expenses()

    def _render_form_buttons(self) -> None:
        for child in self.form_buttons_holder.winfo_children():
            child.destroy()

        if self.selected_expense_index is None:
            self.form_title_var.set("Nova Despesa")
            _style_button(
                self.form_buttons_holder,
                "Adicionar Despesa",
                self._save_expense,
                bg=COLOR_ROSE,
                fg=COLOR_DEEP,
                hover_bg=COLOR_CREAM,
                pady=9,
            ).pack(fill="x", pady=(0, 8))
            _style_button(
                self.form_buttons_holder,
                "Limpar Campos",
                self._reset_form,
                bg=COLOR_DEEP,
                fg=COLOR_CREAM,
                hover_bg=COLOR_TAUPE,
                hover_fg=COLOR_CREAM,
                bold=False,
                pady=7,
            ).pack(fill="x")
        else:
            self.form_title_var.set(f"Editar Despesa #{self.selected_expense_index + 1}")
            _style_button(
                self.form_buttons_holder,
                "Salvar Alterações",
                self._save_expense,
                bg=COLOR_SAGE,
                fg=COLOR_CREAM,
                hover_bg=COLOR_ROSE,
                hover_fg=COLOR_DEEP,
                pady=9,
            ).pack(fill="x", pady=(0, 8))

            row = tk.Frame(self.form_buttons_holder, bg=COLOR_SLATE)
            row.pack(fill="x")
            row.columnconfigure(0, weight=1)
            row.columnconfigure(1, weight=1)

            _style_button(
                row,
                "Excluir",
                self._delete_selected,
                bg=COLOR_ROSE,
                fg=COLOR_DEEP,
                hover_bg=COLOR_CREAM,
                pady=7,
            ).grid(row=0, column=0, sticky="ew", padx=(0, 4))

            _style_button(
                row,
                "Cancelar",
                self._reset_form,
                bg=COLOR_DEEP,
                fg=COLOR_CREAM,
                hover_bg=COLOR_TAUPE,
                hover_fg=COLOR_CREAM,
                bold=False,
                pady=7,
            ).grid(row=0, column=1, sticky="ew", padx=(4, 0))

    def _set_form_feedback(self, message: str, *, success: bool = False) -> None:
        self.form_feedback.configure(
            text=message,
            fg=COLOR_CREAM if success else COLOR_ROSE,
        )

    def _reset_form(self, *, keep_feedback: bool = False) -> None:
        self.selected_expense_index = None
        self.var_category.set("")
        self.var_amount.set("R$ 0,00")
        self.var_date.set(storage.default_date_for_month(self.active_month_key))
        if not keep_feedback:
            self._set_form_feedback("")
        if hasattr(self, "tree"):
            self.tree.selection_remove(self.tree.selection())
        self._render_form_buttons()

    def select_current_month(self, month_key: str) -> None:
        """Altera programaticamente o mês atual exibido no painel."""
        self.active_month_key = month_key
        label = storage.format_month_full_label(month_key)
        self._month_label_to_key[label] = month_key
        if hasattr(self, "var_current_month"):
            self.var_current_month.set(label)
            self._reset_form(keep_feedback=True)
            self._update_month_options()
            self._update_kpis_and_budget()
            self._refresh_table()

    def _on_current_month_selected(self) -> None:
        selected_label = self.var_current_month.get()
        self.active_month_key = self._month_label_to_key.get(
            selected_label, self.active_month_key
        )
        self._reset_form(keep_feedback=True)
        self._update_kpis_and_budget()
        self._refresh_table()

    def _save_salary(self) -> None:
        if not self.current_user:
            return
        try:
            salary = storage.set_user_salary(
                self.current_user, self.var_salary.get(), self.base_dir
            )
            self.var_salary.set(storage.format_brl(salary))
        except storage.ValidationError as exc:
            self._set_form_feedback(str(exc))
            return
        self._update_kpis_and_budget()
        self._set_form_feedback("✓ Salário mensal atualizado!", success=True)

    def _draw_budget_bar(self) -> None:
        if not hasattr(self, "budget_bar"):
            return
        self.budget_bar.delete("all")
        width = self.budget_bar.winfo_width()
        height = self.budget_bar.winfo_height()
        if width <= 2:
            return
        clamped = min(max(self._budget_ratio, 0.0), 1.0)
        fill_w = int(width * clamped)
        fill_color = COLOR_ROSE if (self._budget_over or self._budget_ratio > 0.85) else COLOR_SAGE
        if fill_w > 0:
            self.budget_bar.create_rectangle(0, 0, fill_w, height, fill=fill_color, width=0)

    def _update_month_options(self) -> None:
        month_keys = storage.list_selectable_months(self._all_expenses)
        if self.active_month_key not in month_keys:
            month_keys.append(self.active_month_key)

        self._month_label_to_key = {}
        labels: list[str] = []
        for key in month_keys:
            label = storage.format_month_full_label(key)
            self._month_label_to_key[label] = key
            labels.append(label)

        self.combo_current_month.configure(values=labels)
        self.var_current_month.set(storage.format_month_full_label(self.active_month_key))

    def _update_kpis_and_budget(self) -> None:
        if not self.current_user:
            return

        month_key = self.active_month_key
        month_name = storage.get_month_name(month_key)
        month_expenses = storage.filter_expenses_by_month(self._all_expenses, month_key)
        month_total = storage.calculate_total(month_expenses)
        monthly_avg = storage.calculate_monthly_average(self._all_expenses)

        self.kpi_period_title_var.set(f"Total - {month_name}")
        self.table_title_var.set(f"Despesas de {storage.format_month_full_label(month_key)}")
        self.kpi_total_var.set(storage.format_brl(month_total))
        self.kpi_monthly_avg_var.set(storage.format_brl(monthly_avg))

        salary = storage.get_user_salary(self.current_user, self.base_dir)
        if salary <= Decimal("0.00"):
            self.kpi_available_var.set("Defina o salário")
            self.kpi_debt_var.set("R$ 0,00")
            self.lbl_available_val.configure(fg=COLOR_TAUPE)
            self.lbl_debt_val.configure(fg=COLOR_TAUPE)
            self._budget_ratio = 0.0
            self._budget_over = False
            self.budget_status_var.set(
                f"{month_name}: {storage.format_brl(month_total)} gastos • Informe seu salário para comparar"
            )
        else:
            available, debt = storage.calculate_budget_status(month_total, salary)
            pct = float((month_total / salary) * Decimal("100"))
            self._budget_ratio = float(month_total / salary)
            self._budget_over = debt > Decimal("0.00")

            self.kpi_available_var.set(storage.format_brl(available))
            self.kpi_debt_var.set(storage.format_brl(debt))

            self.lbl_available_val.configure(fg=COLOR_CREAM if available > 0 else COLOR_TAUPE)
            self.lbl_debt_val.configure(fg=COLOR_ROSE if self._budget_over else COLOR_SAGE)

            pct_str = f"{pct:.1f}".replace(".", ",")
            if self._budget_over:
                self.budget_status_var.set(
                    f"{month_name}: limite excedido ({pct_str}% do salário) — Devendo {storage.format_brl(debt)}"
                )
            else:
                self.budget_status_var.set(
                    f"{month_name}: {pct_str}% do salário usado — Ainda pode gastar {storage.format_brl(available)}"
                )

        self._draw_budget_bar()

    def reload_expenses(self) -> None:
        if not self.current_user:
            return
        self._all_expenses = storage.list_expenses(self.current_user, self.base_dir)
        self._update_month_options()
        self._update_kpis_and_budget()
        self._refresh_table()

    def _refresh_table(self) -> None:
        for item in self.tree.get_children():
            self.tree.delete(item)

        query = self.var_search.get().strip().casefold()

        shown: list[tuple[int, storage.Expense]] = []
        for idx, exp in enumerate(self._all_expenses):
            if storage.extract_month_key(exp.expense_date) != self.active_month_key:
                continue
            if not query or query in exp.category.casefold() or query in exp.expense_date.casefold():
                shown.append((idx, exp))

        for display_pos, (real_idx, exp) in enumerate(shown):
            tag = "even" if display_pos % 2 == 0 else "odd"
            self.tree.insert(
                "",
                "end",
                iid=str(real_idx),
                values=(
                    display_pos + 1,
                    exp.category,
                    storage.format_brl(exp.amount),
                    exp.expense_date,
                ),
                tags=(tag,),
            )

        filtered_total = sum((exp.amount for _, exp in shown), start=Decimal("0.00"))
        month_label = storage.format_month_full_label(self.active_month_key)
        if query:
            self.table_footer_var.set(
                f"Exibindo {len(shown)} item(ns) filtrados em {month_label} • Subtotal: {storage.format_brl(filtered_total)}"
            )
        elif shown:
            self.table_footer_var.set(
                f"{len(shown)} lançamento(s) em {month_label} • Clique em uma linha para editar ou excluir."
            )
        else:
            self.table_footer_var.set(
                f"Nenhuma despesa registrada em {month_label}."
            )

    def _on_tree_select(self, _event: object) -> None:
        selection = self.tree.selection()
        if not selection:
            return
        idx = int(selection[0])
        if idx < 0 or idx >= len(self._all_expenses):
            return

        exp = self._all_expenses[idx]
        self.selected_expense_index = idx
        self.var_category.set(exp.category)
        self.var_amount.set(storage.format_brl(exp.amount))
        self.var_date.set(exp.expense_date)
        self._set_form_feedback("")
        self._render_form_buttons()

    def _save_expense(self) -> None:
        if not self.current_user:
            return
        cat = self.var_category.get()
        amount = self.var_amount.get()
        dt = self.var_date.get()

        try:
            if self.selected_expense_index is None:
                created = storage.add_expense(
                    self.current_user,
                    cat,
                    amount,
                    dt,
                    self.base_dir,
                    default_month_key=self.active_month_key,
                )
                saved_mk = storage.extract_month_key(created.expense_date)
                switched = bool(saved_mk and saved_mk != self.active_month_key)
                if saved_mk:
                    self.active_month_key = saved_mk
                self._reset_form(keep_feedback=True)
                if switched and saved_mk:
                    self._set_form_feedback(
                        f"✓ Despesa salva em {storage.format_month_full_label(saved_mk)}!",
                        success=True,
                    )
                else:
                    self._set_form_feedback("✓ Despesa adicionada com sucesso!", success=True)
            else:
                updated = storage.update_expense(
                    self.current_user,
                    self.selected_expense_index,
                    cat,
                    amount,
                    dt,
                    self.base_dir,
                    default_month_key=self.active_month_key,
                )
                saved_mk = storage.extract_month_key(updated.expense_date)
                if saved_mk:
                    self.active_month_key = saved_mk
                self._reset_form(keep_feedback=True)
                self._set_form_feedback("✓ Despesa atualizada com sucesso!", success=True)
        except storage.ValidationError as exc:
            self._set_form_feedback(str(exc))
            return

        self.reload_expenses()

    def _delete_selected(self) -> None:
        if not self.current_user or self.selected_expense_index is None:
            return
        exp = self._all_expenses[self.selected_expense_index]
        confirmed = self.confirm_fn(
            "Confirmar exclusão",
            f"Deseja excluir '{exp.category}' ({storage.format_brl(exp.amount)} em {exp.expense_date})?",
        )
        if not confirmed:
            return

        storage.delete_expense(self.current_user, self.selected_expense_index, self.base_dir)
        self._reset_form(keep_feedback=True)
        self._set_form_feedback("✓ Despesa removida com sucesso!", success=True)
        self.reload_expenses()

    # ------------------------------------------------------------------
    # Tela de Resumo Anual e Detalhes por Mês
    # ------------------------------------------------------------------
    def show_annual_summary(self, username: str) -> None:
        self._clear_container()
        self.current_user = username
        self._all_expenses = storage.list_expenses(username, self.base_dir)

        self._build_top_bar(
            username,
            nav_button_text="← Voltar ao Painel",
            nav_command=lambda: self.show_dashboard(username),
            subtitle_badge="Resumo Anual & Mensal",
        )

        main_area = tk.Frame(self.container, bg=COLOR_DEEP, padx=22, pady=14)
        main_area.pack(fill="both", expand=True)

        # Barra de seleção de ano + 3 KPIs do resumo anual
        years = storage.list_available_years(self._all_expenses)
        default_year = storage.extract_year(f"01/{self.active_month_key}") or years[0]
        if default_year not in years:
            default_year = years[0]

        filter_card = tk.Frame(
            main_area,
            bg=COLOR_SLATE,
            padx=18,
            pady=12,
            highlightthickness=1,
            highlightbackground=COLOR_TAUPE,
        )
        filter_card.pack(fill="x", pady=(0, 12))

        tk.Label(
            filter_card,
            text="Ano de referência:",
            bg=COLOR_SLATE,
            fg=COLOR_ROSE,
            font=(FONT_FAMILY, 10, "bold"),
        ).pack(side="left", padx=(0, 8))

        self.var_summary_year = tk.StringVar(value=str(default_year))
        self.combo_summary_year = ttk.Combobox(
            filter_card,
            textvariable=self.var_summary_year,
            values=[str(y) for y in years],
            state="readonly",
            width=10,
            style="Holst.TCombobox",
        )
        self.combo_summary_year.pack(side="left", padx=(0, 20))
        self.combo_summary_year.bind("<<ComboboxSelected>>", lambda _e: self._refresh_annual_summary())

        tk.Label(
            filter_card,
            text="Selecione um mês na lista abaixo para ver tudo o que gastou naquele mês.",
            bg=COLOR_SLATE,
            fg=COLOR_CREAM,
            font=(FONT_FAMILY, 9),
        ).pack(side="left")

        kpi_row = tk.Frame(main_area, bg=COLOR_DEEP)
        kpi_row.pack(fill="x", pady=(0, 12))
        for col in range(3):
            kpi_row.columnconfigure(col, weight=1, uniform="annual_kpi")

        self.annual_total_title_var = tk.StringVar(value=f"TOTAL DO ANO ({default_year})")
        self.annual_total_var = tk.StringVar(value="R$ 0,00")
        self.annual_monthly_avg_var = tk.StringVar(value="R$ 0,00")
        self.summary_month_title_var = tk.StringVar(value="Total - Novembro")
        self.summary_month_total_var = tk.StringVar(value="R$ 0,00")

        self._build_kpi_card(
            kpi_row, 0, self.annual_total_title_var, self.annual_total_var, COLOR_ROSE, total_columns=3
        )
        self._build_kpi_card(
            kpi_row, 1, "MÉDIA DE GASTO POR MÊS", self.annual_monthly_avg_var, COLOR_CREAM, total_columns=3
        )
        self._build_kpi_card(
            kpi_row, 2, self.summary_month_title_var, self.summary_month_total_var, COLOR_CREAM, total_columns=3
        )

        # Conteúdo dividido: Meses do Ano (esquerda) + Despesas do Mês Selecionado (direita)
        content = tk.Frame(main_area, bg=COLOR_DEEP)
        content.pack(fill="both", expand=True)
        content.columnconfigure(0, weight=0)
        content.columnconfigure(1, weight=1)
        content.rowconfigure(0, weight=1)

        # Esquerda: Tabela de todos os meses do ano
        months_card = tk.Frame(
            content,
            bg=COLOR_SLATE,
            width=410,
            padx=18,
            pady=16,
            highlightthickness=1,
            highlightbackground=COLOR_TAUPE,
        )
        months_card.grid(row=0, column=0, sticky="nsew", padx=(0, 16))
        months_card.grid_propagate(False)

        tk.Label(
            months_card,
            text="Gastos de Cada Mês",
            bg=COLOR_SLATE,
            fg=COLOR_ROSE,
            font=(FONT_FAMILY, 13, "bold"),
            anchor="w",
        ).pack(fill="x", pady=(0, 10))

        months_tree_frame = tk.Frame(months_card, bg=COLOR_DEEP)
        months_tree_frame.pack(fill="both", expand=True)

        self.summary_month_tree = ttk.Treeview(
            months_tree_frame,
            columns=("month", "count", "total", "status"),
            show="headings",
            style="Holst.Treeview",
            selectmode="browse",
        )
        self.summary_month_tree.heading("month", text="Mês", anchor="w")
        self.summary_month_tree.heading("count", text="Qtd.", anchor="center")
        self.summary_month_tree.heading("total", text="Total Gasto", anchor="e")
        self.summary_month_tree.heading("status", text="Salário", anchor="center")

        self.summary_month_tree.column("month", width=110, stretch=True, anchor="w")
        self.summary_month_tree.column("count", width=50, stretch=False, anchor="center")
        self.summary_month_tree.column("total", width=115, stretch=False, anchor="e")
        self.summary_month_tree.column("status", width=85, stretch=False, anchor="center")

        self.summary_month_tree.tag_configure("even", background=COLOR_DEEP, foreground=COLOR_CREAM)
        self.summary_month_tree.tag_configure("odd", background=COLOR_ROW_ALT, foreground=COLOR_CREAM)

        m_scroll = ttk.Scrollbar(
            months_tree_frame,
            orient="vertical",
            command=self.summary_month_tree.yview,
            style="Holst.Vertical.TScrollbar",
        )
        self.summary_month_tree.configure(yscrollcommand=m_scroll.set)
        self.summary_month_tree.pack(side="left", fill="both", expand=True)
        m_scroll.pack(side="right", fill="y")
        self.summary_month_tree.bind("<<TreeviewSelect>>", self._on_summary_month_tree_select)

        # Direita: Detalhes do mês selecionado
        detail_card = tk.Frame(
            content,
            bg=COLOR_SLATE,
            padx=18,
            pady=16,
            highlightthickness=1,
            highlightbackground=COLOR_TAUPE,
        )
        detail_card.grid(row=0, column=1, sticky="nsew")

        detail_top = tk.Frame(detail_card, bg=COLOR_SLATE)
        detail_top.pack(fill="x", pady=(0, 10))

        self.detail_title_var = tk.StringVar(value="Gastos do Mês")
        tk.Label(
            detail_top,
            textvariable=self.detail_title_var,
            bg=COLOR_SLATE,
            fg=COLOR_ROSE,
            font=(FONT_FAMILY, 13, "bold"),
        ).pack(side="left")

        month_pick_box = tk.Frame(detail_top, bg=COLOR_SLATE)
        month_pick_box.pack(side="right")
        tk.Label(
            month_pick_box,
            text="Ver mês:",
            bg=COLOR_SLATE,
            fg=COLOR_CREAM,
            font=(FONT_FAMILY, 9, "bold"),
        ).pack(side="left", padx=(0, 6))

        self._summary_month_names = [storage.MONTH_FULL_NAMES_PT[m] for m in range(1, 13)]
        initial_month_num = int(self.active_month_key.split("/")[0])
        self.var_summary_month = tk.StringVar(value=storage.MONTH_FULL_NAMES_PT[initial_month_num])
        self.combo_summary_month = ttk.Combobox(
            month_pick_box,
            textvariable=self.var_summary_month,
            values=self._summary_month_names,
            state="readonly",
            width=14,
            style="Holst.TCombobox",
        )
        self.combo_summary_month.pack(side="left")
        self.combo_summary_month.bind(
            "<<ComboboxSelected>>", lambda _e: self._on_summary_month_combo_select()
        )

        detail_tree_frame = tk.Frame(detail_card, bg=COLOR_DEEP)
        detail_tree_frame.pack(fill="both", expand=True)

        self.detail_tree = ttk.Treeview(
            detail_tree_frame,
            columns=("num", "category", "amount", "date"),
            show="headings",
            style="Holst.Treeview",
            selectmode="browse",
        )
        self.detail_tree.heading("num", text="#", anchor="center")
        self.detail_tree.heading("category", text="Categoria", anchor="w")
        self.detail_tree.heading("amount", text="Valor (R$)", anchor="e")
        self.detail_tree.heading("date", text="Data", anchor="center")

        self.detail_tree.column("num", width=44, stretch=False, anchor="center")
        self.detail_tree.column("category", width=250, stretch=True, anchor="w")
        self.detail_tree.column("amount", width=130, stretch=False, anchor="e")
        self.detail_tree.column("date", width=105, stretch=False, anchor="center")

        self.detail_tree.tag_configure("even", background=COLOR_DEEP, foreground=COLOR_CREAM)
        self.detail_tree.tag_configure("odd", background=COLOR_ROW_ALT, foreground=COLOR_CREAM)

        d_scroll = ttk.Scrollbar(
            detail_tree_frame,
            orient="vertical",
            command=self.detail_tree.yview,
            style="Holst.Vertical.TScrollbar",
        )
        self.detail_tree.configure(yscrollcommand=d_scroll.set)
        self.detail_tree.pack(side="left", fill="both", expand=True)
        d_scroll.pack(side="right", fill="y")

        self.detail_footer_var = tk.StringVar(value="")
        tk.Label(
            detail_card,
            textvariable=self.detail_footer_var,
            bg=COLOR_SLATE,
            fg=COLOR_TAUPE,
            font=(FONT_FAMILY, 9),
            anchor="w",
        ).pack(fill="x", pady=(10, 0))

        self._refresh_annual_summary()

    def select_summary_month(self, month_num: int, year: int | None = None) -> None:
        """Seleciona um mês (1-12) e opcionalmente o ano na tela de resumo anual."""
        if year is not None:
            self.var_summary_year.set(str(year))
        self.var_summary_month.set(storage.MONTH_FULL_NAMES_PT[month_num])
        self._refresh_annual_summary()

    def _on_summary_month_tree_select(self, _event: object) -> None:
        sel = self.summary_month_tree.selection()
        if not sel:
            return
        month_key = sel[0]
        self.var_summary_month.set(storage.get_month_name(month_key))
        self._refresh_summary_month_details()

    def _on_summary_month_combo_select(self) -> None:
        year = int(self.var_summary_year.get())
        month_name = self.var_summary_month.get()
        month_num = self._summary_month_names.index(month_name) + 1
        month_key = f"{month_num:02d}/{year}"
        if self.summary_month_tree.exists(month_key):
            self.summary_month_tree.selection_set(month_key)
            self.summary_month_tree.see(month_key)
        self._refresh_summary_month_details()

    def _refresh_annual_summary(self) -> None:
        if not self.current_user:
            return
        year = int(self.var_summary_year.get())
        year_expenses = storage.filter_expenses_by_year(self._all_expenses, year)
        year_total = storage.calculate_total(year_expenses)
        year_avg = storage.calculate_monthly_average(year_expenses)

        self.annual_total_title_var.set(f"TOTAL DO ANO ({year})")
        self.annual_total_var.set(storage.format_brl(year_total))
        self.annual_monthly_avg_var.set(storage.format_brl(year_avg))

        salary = storage.get_user_salary(self.current_user, self.base_dir)
        rows = storage.summarize_year_by_month(self._all_expenses, year)

        for item in self.summary_month_tree.get_children():
            self.summary_month_tree.delete(item)

        for idx, (month_key, month_name, count, total) in enumerate(rows):
            tag = "even" if idx % 2 == 0 else "odd"
            if salary <= Decimal("0.00") or count == 0:
                status = "-"
            elif total > salary:
                status = "Excedeu"
            else:
                status = "No limite"

            self.summary_month_tree.insert(
                "",
                "end",
                iid=month_key,
                values=(month_name, count, storage.format_brl(total), status),
                tags=(tag,),
            )

        selected_name = self.var_summary_month.get()
        month_num = (
            self._summary_month_names.index(selected_name) + 1
            if selected_name in self._summary_month_names
            else 1
        )
        selected_key = f"{month_num:02d}/{year}"
        if self.summary_month_tree.exists(selected_key):
            self.summary_month_tree.selection_set(selected_key)
            self.summary_month_tree.see(selected_key)

        self._refresh_summary_month_details()

    def _refresh_summary_month_details(self) -> None:
        year = int(self.var_summary_year.get())
        month_name = self.var_summary_month.get()
        month_num = self._summary_month_names.index(month_name) + 1
        month_key = f"{month_num:02d}/{year}"

        month_expenses = storage.filter_expenses_by_month(self._all_expenses, month_key)
        month_total = storage.calculate_total(month_expenses)

        self.summary_month_title_var.set(f"Total - {month_name}")
        self.summary_month_total_var.set(storage.format_brl(month_total))
        self.detail_title_var.set(f"Gastos de {month_name}/{year}")

        for item in self.detail_tree.get_children():
            self.detail_tree.delete(item)

        for idx, exp in enumerate(month_expenses):
            tag = "even" if idx % 2 == 0 else "odd"
            self.detail_tree.insert(
                "",
                "end",
                values=(idx + 1, exp.category, storage.format_brl(exp.amount), exp.expense_date),
                tags=(tag,),
            )

        if month_expenses:
            self.detail_footer_var.set(
                f"{len(month_expenses)} lançamento(s) em {month_name}/{year} • Total: {storage.format_brl(month_total)}"
            )
        else:
            self.detail_footer_var.set(f"Nenhum gasto registrado em {month_name}/{year}.")


def launch(*, base_dir: Path = storage.BASE_DIR) -> None:
    """Inicia a janela desktop do aplicativo."""
    root = tk.Tk()
    _enable_windows_dpi_and_dark_titlebar(root)
    ExpenseApp(root, base_dir=base_dir)
    root.mainloop()


if __name__ == "__main__":
    launch()
