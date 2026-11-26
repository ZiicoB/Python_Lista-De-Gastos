# Lista de Gastos (Python)

Aplicativo de controle financeiro pessoal em Python (com interface gráfica desktop e modo opcional de terminal), originalmente desenvolvido como projeto avaliativo da cadeira de Python na **CESAR School**.

Permite que usuários autenticados registrem, editem, filtrem e acompanhem seus gastos mensais e anuais com comparativo em relação ao salário mensal.

---

## Principais Funcionalidades

* **Autenticação e Segurança:** Cadastro e login de usuários com senhas protegidas por hash `PBKDF2-HMAC-SHA256` (com salt) e opção **Salvar login** via token local protegido por **Windows DPAPI** (`CryptProtectData`).
* **Interface Desktop (Tkinter — Paleta Holst):** Janela nativa fora do CMD usando a paleta `#1E293B`, `#334155`, `#5C6B66`, `#8A7D7B`, `#C8A99D` e `#F2E6D6`.
* **Gestão de Despesas:** Cadastro, edição, busca por texto e exclusão de lançamentos com validação de categoria, data (`DD/MM` ou `DD/MM/AAAA`) e precisão decimal (`Decimal`).
* **Digitação em Moeda Real:** Campos de valor e salário com máscara automática de centavos (`25` → `R$ 0,25`, `2500` → `R$ 25,00`).
* **Controle Mensal e Orçamento:** Seletor de **Mês atual** (`Total - Mês`), cálculo da **Média de Gasto Mensal**, cadastro de **Salário Mensal**, barra de progresso e indicação automática de **saldo disponível** ou **valor excedente (quanto vai ficar devendo)**.
* **Resumo Anual e por Mês:** Tela dedicada com os gastos dos 12 meses do ano selecionado, total anual, média mensal e listagem detalhada dos lançamentos de cada mês.

---

## Requisitos

* Python 3.10+ (utiliza apenas a biblioteca padrão do Python, incluindo `tkinter`).

---

## Como Executar

Abrir o aplicativo desktop pelo CMD:

```bat
python Menu.py
```

Abrir sem manter uma janela do CMD presa/visível:

```bat
start pythonw ListaDeGastos.pyw
```

Executar no modo de terminal (CLI):

```bat
python Menu.py --cli
```

---

## Estrutura do Projeto

* `app_gui.py`: Interface gráfica desktop (Tkinter) com telas de login, painel mensal e resumo anual.
* `ListaDeGastos.pyw`: Atalho Windows sem console para abrir o aplicativo diretamente.
* `Menu.py`: Ponto de entrada principal (abre a GUI por padrão) e interface CLI (`--cli`).
* `ui.py`: Componentes visuais TrueColor (paleta Holst) e suporte UTF-8/ANSI para o modo CLI.
* `storage.py`: Persistência em CSV (`utf-8`), validações, cálculos financeiros, hash de senhas e token de sessão.
* `Usuarios.csv`: Base de usuários cadastrados.
* `Arquivos/`: Arquivos CSV de despesas por usuário, salários e sessão local.
* `tests/test_app.py`: Suíte de testes unitários e de fluxo (`unittest`).

---

## Testes

```bat
python -m unittest discover -s tests -v
```

---

## Registro de Atualizações

### 25/11/2026 *(feito com IA)*
* Correção de bugs críticos de fluxo (recursão infinita entre menus, validação de duplicidade e leitura/escrita em CSV), segurança (hash `PBKDF2` nas senhas, prevenção de *path traversal* e validação de entradas/datas) e limpeza do `.gitignore`.
* Criação da interface gráfica desktop com a paleta Holst (`app_gui.py` e `ListaDeGastos.pyw`) e opção de salvar login com token protegido por DPAPI.
* Implementação da máscara de moeda em centavos (`25` → `R$ 0,25`), seletor de mês atual (`Total - Mês`), média de gasto mensal, comparativo com salário/dívida excedente e tela de resumo anual/mensal.
* Adição da suíte de testes automatizados em `tests/test_app.py`.
