import os
os.system("cls")

separador = "=-=" * 11
cor1 = "\033[34m"
fimcor = "\033[m"
#\033 | 31m => Vermelho |32m => Verde |33m => Amarelo 34m=> Azul | 

def main():
    while True:
        print(f"\n{cor1}{separador}{fimcor}")
        print("{:^34}".format("Menu Principal"))
        print(f"\033[34m{separador}\033[m\n")
        
        print("1 - Login do Usuário")
        print("2 - Criar novo Usuário")
        print("0 - Encerar sistema\n")

        menuinicial = input("Digite sua opção: ")
        
        if menuinicial == '1':
            login_usuario()
        elif menuinicial == '2':
            novo_usuario() 
        elif menuinicial == '0':
            os.system("cls")
            print ("\n\033[31mSISTEMA ENCERRADO.\033[m \n", "\n\033[32mDados salvos com sucesso!\033")
            raise SystemExit
        elif menuinicial != '1' or menuinicial != '2' or menuinicial != '0':
            print("\033[31mOpção inválida.\033[m")
        else:
            print("\033[31mOpção inválida.\033[m")


def login_usuario():
    while True:
        print(f"\n\033[34m{separador}\033[m")
        print("{:^34}".format("Sistema de Login"))
        print(f"\033[34m{separador}\033[m\n")
        
        with open(f'{os.getcwd()}/Usuarios.csv', 'rt+') as docLogins:
            linhas = docLogins.readlines()

        nick = input("Seu o Login: ")

        for usuario in linhas:
            conta = usuario.strip().split(',')
            if conta[0] == nick:
                senha = input('Digite sua senha: ')
                if senha == conta[1]:
                    menu_cliente(nick)
                else:
                    print(f"\033[34m{separador}\033[m")
                    print("{:^34}".format("Usuário ou Senha errado."))
                    print(f"\033[34m{separador}\033[m\n")
                    print("1 - Tentar novamente.")
                    print("2 - Criar novo Usuário.")
                    print("0 - Voltar\n")

                    opcaoNaoExiste = input("Digite sua Opção: ")

                    if opcaoNaoExiste == '1':
                        print()
                    elif opcaoNaoExiste == '2':
                        novo_usuario()
                    elif opcaoNaoExiste == '0':
                        main()
                    else:
                        print("\033[31mOpção inválida.\033[m")


def novo_usuario():
    while True:
        print(f"\n\033[34m{separador}\033[m")
        print("{:^34}".format("Novo Usuario"))
        print(f"\033[34m{separador}\033[m\n")

        novaConta = open(f'{os.getcwd()}/Usuarios.csv', 'rt+')

        texto = novaConta.read()
        lertexto = texto.split('\n')
        usuarios = [linha.split(', \n')[0] for linha in lertexto]
        #Verifica por linha, os usuarios existentes
        novoNick = input("Novo Usuário: ")
        #Caso seja encontrado algum usuario igual ele nao deixa criar
        if novoNick in usuarios:
            print("\033[31m Este usuário já existe.\nTente criar outro nome!\033[m\n")
            novaConta.close()
        else:
            novaSenha = input("Senha: ")
            novaConta.write(f"{novoNick},{novaSenha}\n")
            print("\033[33mNovo usuário criado.\033[m")
            novaConta.close()
            main()


def menu_cliente(nick):
    while True:
        try:
            print(f"\n\033[34m{separador}\033[m")
            print("{:^38}".format(f"Usuario - \033[33m{nick}\033[m")) 
            print(f"\033[34m{separador}\033[m\n")

            listadoUsuario = f"Arquivos/{nick}.csv"        
            with open(listadoUsuario, 'a') as arquivo:
                arquivo.write("")
                arquivo.close()
                    
            print("1 - Adicionar Despesa")
            print("2 - Editar Despesa")
            print("3 - Mostrar Despesas")
            print("0 - Sair do Usuario\n")

            menuCliente = input("Digite sua opção: ")

            if menuCliente == '1':
                print()
                criar_tabela(nick)
            elif menuCliente == '2':
                editar_despesa(nick)
            elif menuCliente == '3':
                mostrar_despesa(nick)
            elif menuCliente == '0':
                main()
            elif menuCliente != '1' or menuCliente != '2' or menuCliente != '0':
                print("\033[31mOpção inválida.\033[m")
        except ValueError:
            print()
            

def criar_tabela(nick):
    while True:
        print(f"\033[34m{separador}\033[m")
        print("{:^33}".format("Nova Lista"))
        print(f"\033[34m{separador}\033[m\n")

        listadoUsuario = f"Arquivos/{nick}.csv"
        
        with open(listadoUsuario, 'a') as arquivo:
            categoria = input("Tipo de Despesa: ")
            valor = float(input("Valor: "))
            dia = input("Dia/Mês: ")

            arquivo.write(f"{nick},{categoria},{valor},{dia}\n")
            print("\nDespesa adicionada com sucesso!\n")
            arquivo.close()

            print("1 - Adicionar novamente")
            print("0 - Voltar\n")
            repetirAdd = input("Digite sua Opção: ")

            if repetirAdd == '1':
                print()
            elif repetirAdd == '0':
                menu_cliente(nick)
            else:
                print("\033[31mOpção inválida.\033[m")


def editar_despesa(nick):
    while True:
        print(f"\n\033[34m{separador}\033[m")
        print("{:^34}".format("Editar Despesas"))
        print(f"\033[34m{separador}\033[m\n")

        listadoUsuario = f"Arquivos/{nick}.csv"
        
        with open(listadoUsuario, "r+") as docListas:
            linhas = docListas.readlines()

            print("{:<2} | {:<25} | {:<25} | {}".format("","\033[33mCategoria\033[m","\033[33mValor\033[m","\033[33mDia\033[m\n"))

            for i, usuario in enumerate(linhas):
                conta = usuario.strip().split(',')
                if conta[0] == nick:
                    usuario = conta[0]
                    categoria = conta[1]
                    valor = conta[2]
                    dia = conta[3]

                    catFormatada = "- {:<19} R${:<17} {}".format(categoria.upper(), valor, dia, "")
                    print(f"{i + 1} {catFormatada}")
            print("\nVoltar (Enter)")
            editarCat = int(input("Numero da Categoria: "))-1

            if editarCat >= 0 and editarCat < len(linhas):
                numeroLinha = linhas[editarCat]
                conta = numeroLinha.strip().split(',')

                print("1 - Alterar")
                print("2 - Deletar")
                print("0 - Voltar Menu\n")

                editartudo = input("Qual sua Opção: ")
                
                if editartudo == '1':

                    editaCategoria = input("Nome da categoria: ")
                    editarValor = float(input("Novo valor: "))
                    EditarDia = input("Qual dia: ")

                    conta[1] = editaCategoria
                    conta[2] = editarValor
                    conta[3] = EditarDia
                    linhas[editarCat] = ",".join(map(str, conta)) + "\n"
                    # Atualiza a linha no arquivo
                    print("Linha atualizada com sucesso!")
                    docListas.close()

                elif editartudo == '2':
                    del linhas[editarCat]
                    print("Linha deletada com sucesso!")
                elif editartudo == '0':
                    docListas.close()
                    menu_cliente(nick)
                elif editartudo != '1' or editartudo != '2' or editartudo != '0':
                    print("\033[31mOpção inválida.\033[m")
            else:
                debug = input("Tentar Novamente (Enter)")
                if debug != '1':
                    menu_cliente(nick)

        # Sobrescrever o arquivo com as alterações
        with open(listadoUsuario, "w") as docListas:
            docListas.writelines(linhas) 


def mostrar_despesa(nick):
    print(f"\n\033[34m{separador}\033[m")
    print("{:^34}".format("Total Despesas"))
    print(f"\033[34m{separador}\033[m\n")

    listadoUsuario = f"Arquivos/{nick}.csv"

    with open(listadoUsuario, "r+") as docListas:
        linhas = docListas.readlines()

        print("| {:<25} | {:<25} | {}".format("\033[33mCategoria\033[m","\033[33mValor\033[m","\033[33mDia\033[m\n"))

        for i, usuario in enumerate(linhas):
            conta = usuario.strip().split(',')
            if conta[0] == nick:
                usuario = conta[0]
                categoria = conta[1]
                valor = conta[2]
                dia = conta[3]

                catFormatada = "{:<20} R${:<17} {}".format(categoria.upper(), valor, dia, "")
                print(catFormatada)

        somaDasDespesas = 0 
        for usuario in linhas:
            conta = usuario.strip().split(',')
            valor = float(conta[2])  
            somaDasDespesas += valor

        print("\nDespesas totais: R$ ", somaDasDespesas)

        voltando = input("\nVoltar (Enter)")

        if voltando == '1':
            menu_cliente(nick)
            

while True:
    print(f"\033[34m{separador}\033[m\n")
    inicar = input("{:^34}".format("ENTER PARA INICIAR"))
    if inicar != "9xrtz5pr":
        main()
    else:
        print("\033[31mOpção inválida.\033[m")
