# Importações
import pandas as pd
import os
from pathlib import Path
import re
import sqlite3
from datetime import datetime
import numpy as np
from sklearn.linear_model import LinearRegression
import matplotlib.pyplot as plt
from matplotlib.ticker import MaxNLocator
import matplotlib.dates as mdates
from dateutil import parser

# Variáveis responsáveis pelo acesso às pastas
PASTA_ENTRADA = 'Entrada'
PASTA_SAIDA = 'Saida'
PASTA_ESTOQUE = os.path.join(PASTA_ENTRADA, 'Estoque')
PASTA_VENDAS = os.path.join(PASTA_ENTRADA,'Vendas')
BANCO_DE_DADOS = 'geral.db'

# Nome das contas (usado para acessar as subpastas)
CONTAS = {
    'A':'Braza',
    'B':'Distribuidao',
    'C':'Gab',
    'D':'Prodoo',
}

# Banco de dados
def banco_dados():
    #criando banco de dados
    conn = sqlite3.connect(BANCO_DE_DADOS)
    CURSOR = conn.cursor()

    CURSOR.execute("""
    CREATE TABLE vendas (
                   id INTEGER NOT NULL PRIMARY KEY AUTOINCREMENT,
                   sku TEXT,
                   quantidade_itens INTEGER,
                   quantidade_total INTEGER,
                   quantidade INTEGER,
                   data DATE,
                   contas TEXT                  
    );
    """)
    CURSOR.execute("""
    CREATE TABLE estoque (
                   id INTEGER NOT NULL PRIMARY KEY AUTOINCREMENT,
                   sku TEXT,
                   quantidade_itens INTEGER,
                   quantidade_estoque INTEGER,
                   data DATE
                                    
    );
    
    """)
    CURSOR.execute("""
    CREATE TABLE previsão_futura (
                    id INTEGER NOT NULL PRIMARY KEY AUTOINCREMENT,
                    sku TEXT,
                    data TEXT,
                    quantidade_prevista FLOAT,
                    conta TEXT          
                   );
    """)
    print("Tabela criada com exito")
    #fechando a sessão
    conn.close()

# Traduzir datas que estão em inglês para português
def traduzir_data(data_str):
    meses = {
        'janeiro': 'january', 'fevereiro': 'february', 'março': 'march', 'abril': 'april',
        'maio': 'may', 'junho': 'june', 'julho': 'july', 'agosto': 'august',
        'setembro': 'september', 'outubro': 'october', 'novembro': 'november', 'dezembro': 'december'
    }
    
    if isinstance(data_str, str):
        for pt, en in meses.items():
            data_str = data_str.lower().replace(pt, en)
        try:
            return parser.parse(data_str, fuzzy=True)
        except:
            return pd.NaT
    return pd.NaT

# para manter a data atual no estoque
def data():
    data_f = datetime.today()
    data_atual = data_f.strftime("%Y-%m-%d")
    return data_atual

# responsável por apontar o proximo passo a se segrir
def chamar_funcao_banco():
    if not os.path.exists(BANCO_DE_DADOS):
        banco_dados()
    else:
        banco_existe

# Se banco existir, vai deletar toda a tabela do estoque para subistituir com os dados de estoque atualizados
def banco_existe(novos_dados : dict):
    conn = sqlite3.connect(BANCO_DE_DADOS)
    cursor = conn.cursor()

    data_atual = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    # Atualiza TABELAS comuns (acrescenta com data)
    for tabela, df in novos_dados.items():
        if tabela == 'estoque':
            # Descarta dados antigos e insere novos
            cursor.execute(f"DROP TABLE IF EXISTS {tabela}")
            df.to_sql(tabela, conn, index=False)
            print(f"Tabela '{tabela}' recriada com novos dados.")
        else:
            df['data'] = data_atual
            try:
                df.to_sql(tabela, conn, if_exists='append', index=False)
                print(f"Tabela '{tabela}' atualizada.")
            except Exception as e:
                print(f"Erro ao atualizar tabela '{tabela}': {e}")

    conn.commit()
    conn.close()

# Trata a sku para separ a quantidade do número do produto
def tratar_SKU(sku):
    # Verifica se o valor do SKU é nulo (NaN). Se for, retorna duas vezes None.
    if pd.isna(sku):
        return None, None
    try:
        # Converte o SKU para string e remove espaços em branco nas extremidades.
        sku = str(sku).strip()
        # Separa o SKU usando o hífen como delimitador.
        partes = re.split(r'[-]', sku)

        # Se o SKU foi dividido exatamente em duas partes, retorna ambas, já limpas.
        if len(partes) == 2:
            parte1 = partes[0].strip()
            parte2 = partes[1].strip()

            # Corrige se parte1 for maior que 1
            try:
                if int(parte1) > 1:
                    parte1 = '0'
            except ValueError:
                # Caso parte1 não seja número, você decide o que fazer (ignorar, ou também colocar como '0')
                parte1 = '0'

            return parte1, parte2

        else:
            # Se não tem exatamente duas partes, retorna None para a primeira parte e o SKU inteiro na segunda.
            return None, sku
    except Exception as e:
        # Em caso de erro inesperado, exibe uma mensagem e retorna None para ambas as partes.
        print(f"Erro ao tratar SKU: {e}")
        return None, None

# Faz a previsão das vendas para 360 dias, usando uma funsão linear quadratica 
def comparacao_previsao_vendas(sku_desejado, conta_desejada=None, retornar_dados=False):  
    conn = sqlite3.connect(BANCO_DE_DADOS)
    if conta_desejada:
        query = "SELECT sku, data, quantidade, contas FROM vendas WHERE sku = ? AND contas = ? ORDER BY data"
        params = (sku_desejado, conta_desejada)
    else:
        query = "SELECT sku, data, quantidade, contas FROM vendas WHERE sku = ? ORDER BY data"
        params = (sku_desejado,)

    vendas = pd.read_sql_query(query, conn, params=params)
    conn.close()

    if vendas.empty:
        print(f"Não há dados suficientes para SKU '{sku_desejado}'" + (f" e conta '{conta_desejada}'." if conta_desejada else "."))
        return (None, None, None) if retornar_dados else None

    vendas['data'] = pd.to_datetime(vendas['data'])

    # Agrupa vendas por data, somando quantidade
    grupo = vendas.groupby('data')['quantidade'].sum().reset_index()

    grupo = grupo.sort_values('data').reset_index(drop=True)

    # Frequência diária, preenchendo dias sem venda com zero
    grupo = grupo.set_index('data').asfreq('D', fill_value=0).reset_index()

    # Criar coluna t = número sequencial de dias a partir de zero
    grupo['t'] = (grupo['data'] - grupo['data'].min()).dt.days

    # Termo quadrático para captar tendência curva
    grupo['t2'] = grupo['t'] ** 2

    X = grupo[['t', 't2']]
    y = grupo['quantidade']

    modelo = LinearRegression().fit(X, y)

    # Criar dias futuros (360 dias)
    dias_futuros = np.arange(grupo['t'].max() + 1, grupo['t'].max() + 361)
    dias_futuros_df = pd.DataFrame({'t': dias_futuros, 't2': dias_futuros ** 2})

    # Previsões para os próximos 360 dias (valores >= 0)
    vendas_previstas = modelo.predict(dias_futuros_df)
    vendas_previstas = np.maximum(vendas_previstas, 0)

    previsoes_todas = []

    for (conta, sku), grupo in vendas.groupby(['contas', 'sku']):
        grupo = grupo.copy()
        grupo['data'] = pd.to_datetime(grupo['data'])

        # Pega a última data com registro
        ultima_data = grupo['data'].max()

        # Cria 360 dias futuros a partir do dia seguinte
        datas_futuras = pd.date_range(start=ultima_data + pd.Timedelta(days=1), periods=360)

        df_previsao = pd.DataFrame({
            'sku': sku,
            'data': datas_futuras.strftime('%Y-%m-%d'),
            'quantidade_prevista': vendas_previstas,
            'conta': conta
        })

        previsoes_todas.append(df_previsao)

    # Depois do loop que cria cada df_previsao e adiciona em previsoes_todas:
    df_previsao = pd.concat(previsoes_todas, ignore_index=True)

    # Salvar previsões no banco - primeiro apagar previsões antigas para esse sku e conta
    conn = sqlite3.connect(BANCO_DE_DADOS)
    cursor = conn.cursor()

    # Apagar previsões antigas para os SKUs e contas presentes na nova previsão
    for (conta, sku) in df_previsao[['conta', 'sku']].drop_duplicates().values:
        cursor.execute("""
            DELETE FROM previsão_futura WHERE sku = ? AND conta = ?
        """, (sku, conta))

    # Inserir novas previsões
    for _, row in df_previsao.iterrows():
        cursor.execute("""
            INSERT INTO previsão_futura (sku, data, quantidade_prevista, conta)
            VALUES (?, ?, ?, ?)
        """, (row['sku'], row['data'], row['quantidade_prevista'], row['conta']))

    conn.commit()
    conn.close()

    if retornar_dados:
        return grupo, vendas_previstas, sku_desejado

# Toda vez que há novos dados a tabela de previsão futura precisa ser atualizada com as novas informações para mais precisão
def gerar_todas_previsoes():
    with sqlite3.connect(BANCO_DE_DADOS) as conn:
        conn.execute("DELETE FROM previsão_futura")
        conn.commit()
        print("Dados antigos apagados da tabela 'previsão_futura'.")
        vendas = pd.read_sql_query("SELECT DISTINCT sku, contas FROM vendas", conn)

    for _, row in vendas.iterrows():
        sku = row['sku']
        conta = row['contas']
        comparacao_previsao_vendas(sku, conta)

# Faz a previsão do estoque, com base nas previsões futuras já existentes
def previsao_estoque(sku_desejado, retornar_dados=False):  
    conn = sqlite3.connect(BANCO_DE_DADOS)

    # Dados históricos
    estoque = pd.read_sql_query(
        "SELECT sku, data, quantidade_estoque FROM estoque WHERE sku = ?",
        conn, params=(sku_desejado,))
    estoque['data'] = pd.to_datetime(estoque['data'])

    # Previsão futura de vendas
    pv = pd.read_sql_query(
        "SELECT sku, data, quantidade_prevista FROM previsão_futura WHERE sku = ? ORDER BY data",
        conn, params=(sku_desejado,))
    pv['data'] = pd.to_datetime(pv['data'])

    conn.close()

    if estoque.empty or not estoque['sku'].isin({sku_desejado}).any():
        print(f"Não há dados suficientes para SKU '{sku_desejado} ou ela não existe no estoque!'")
        return (None, None) if retornar_dados else None

    # Último estoque registrado
    ultima_data = pv['data'].min()
    estoque_atual = estoque['quantidade_estoque'].values[0]

    # Criar vetor de datas futuras
    datas_futuras = pd.date_range(start=ultima_data + pd.Timedelta(days=1), periods=360)

    # Criar Series com vendas previstas (indexadas por data)
    pv = pv.groupby('data', as_index=False)['quantidade_prevista'].sum()
    vendas_previstas = pv.set_index('data')['quantidade_prevista'].reindex(datas_futuras, fill_value=0.0)

    # Calcular estoque dia a dia
    estoque_previsto = []
    for venda in vendas_previstas:
        if estoque_atual - venda >= 0:
            estoque_atual = estoque_atual - venda
        else:
            estoque_atual = 0
        estoque_previsto.append(estoque_atual)

    # Agrupar histórico para o retorno
    grupo = estoque.groupby('data')['quantidade_estoque'].sum().reset_index()
    grupo = grupo.set_index('data').asfreq('D', fill_value=0.0).reset_index()

    if retornar_dados:
        return grupo, estoque_previsto, sku_desejado

# Traz os arquivos do estoque
def g_arquivos_estoque():
    lista_estoque = []
    
    for nome_conta in CONTAS.values():
        conta = ''.join(nome_conta.split())  # Remove espaços
        caminho_conta = os.path.join(PASTA_ESTOQUE, conta)

        if not os.path.isdir(caminho_conta):
            print(f"Pasta não encontrada: {caminho_conta}")
            continue

        for nome_arquivo in os.listdir(caminho_conta):
            caminho_arquivo = os.path.join(caminho_conta, nome_arquivo)

            if nome_arquivo.__contains__('full'):
                continue

            # Verifica se é um arquivo CSV
            if os.path.isfile(caminho_arquivo) and nome_arquivo.endswith('.csv'):
                try:
                    df = pd.read_csv(caminho_arquivo,  sep=';', on_bad_lines='skip')
                    print(f"Arquivo lido com sucesso: {caminho_arquivo}")
                    if 'Código' in df.columns:
                        df.rename(columns={'Código': 'SKU'}, inplace=True)
                        df['SKU'] = df['SKU'].str.split(' ').explode('SKU')
                        #trata o sku e adiciona ele a df
                        df[['quantidade_itens', 'sku']] = df['SKU'].apply(lambda x: pd.Series(tratar_SKU(x)))
                        df['quantidade_itens'] = pd.to_numeric(df['quantidade_itens'], errors='coerce').fillna(0).astype(int)
                        # PEGA A COLUNA DE ESTOQUE
                        df['quantidade_estoque'] = df['Estoque']
                        df['quantidade_estoque'] = df['quantidade_estoque'].astype(str).str.replace(',', '.', regex=False).str.strip()
                        df['quantidade_estoque'] = pd.to_numeric(df['quantidade_estoque'], errors='coerce').fillna(0.0).astype(float)
                        df['data'] = str(data())
                        # só da um append nas colunas nessessárias
                        lista_estoque.append(df[['sku', 'quantidade_itens', 'quantidade_estoque', 'data']])
                        df_all = pd.concat(lista_estoque, ignore_index=False)
                        df_all = df_all.groupby(['sku']).agg({
                            'quantidade_estoque' : 'sum'
                        
                        }).reset_index()

                except Exception as e:
                    print(f"Erro ao ler {caminho_arquivo}: {e}")

    if lista_estoque:
        df_all = pd.concat(lista_estoque, ignore_index=False)
        df_all = df_all.groupby(['sku', 'data']).agg({
            'quantidade_estoque' : 'sum',
            'quantidade_itens' : 'sum'                        
        }).reset_index()

        # conexão com o banco de dados para enviar para a tabela 'estoque'
        with sqlite3.connect(BANCO_DE_DADOS) as conn:
            cursor = conn.cursor()
            for _, row in df_all.iterrows():
                cursor.execute("""
                    INSERT INTO estoque (sku, 'quantidade_itens', 'quantidade_estoque', 'data')
                    VALUES (?, ?, ?, ?)
                """, (row['sku'], row['quantidade_itens'], row['quantidade_estoque'], row['data']))
            conn.commit()
            print("Dados inseridos com sucesso no banco.") 
            banco_existe({'estoque': df_all})

# Traz os arquivos das vendas
def g_arquivos_vendas(): 
    file_list = []

    # Separar os nomes das contas para direcionar caminho                                 
    for contas in CONTAS.values():
        contas = contas.split()
        contas = ''.join(contas)  # converte lista para string
        CAMINHO_SUB_VENDAS = os.path.join(PASTA_VENDAS, contas)  # caminho para as sub_pastas
        
        # Pega apenas os arquivos relevantes
        for file in os.listdir(CAMINHO_SUB_VENDAS):
            caminho_sub_vendas = os.path.join(CAMINHO_SUB_VENDAS, file)

            if 'Vendas' in file and 'BR' in file:
                df = pd.read_excel(caminho_sub_vendas, header=5, engine='openpyxl')

                # Traduz e normaliza data
                df['data'] = pd.to_datetime(df['Data da venda'].apply(traduzir_data), errors='coerce')

                # Guarda o SKU original antes do explode
                df['SKU_original'] = df['SKU']

                # Explode a coluna SKU
                df['SKU'] = df['SKU'].astype(str).str.split(' ')
                df = df.explode('SKU').reset_index(drop=True)

                # Preenche datas ausentes com a última data conhecida dentro do SKU original
                df['data'] = df.groupby('SKU_original')['data'].transform(lambda x: x.ffill().bfill())

                # Formata data para string
                df['data'] = df['data'].dt.strftime('%Y-%m-%d')

                # Aplica função de tratamento de SKU (retorna quantidade e SKU limpo)
                df[['quantidade_itens', 'sku']] = df['SKU'].apply(lambda x: pd.Series(tratar_SKU(x)))

                # Remove linhas com SKU inválido
                df = df[df['sku'].notnull() & (df['sku'] != '')]

                # Conversões seguras
                df['quantidade_itens'] = pd.to_numeric(df['quantidade_itens'], errors='coerce').fillna(0).astype(int)
                df['Unidades'] = pd.to_numeric(df['Unidades'], errors='coerce').fillna(0).astype(int)

                # Cálculo total e colunas extras
                df['quantidade_total'] = df['quantidade_itens'] * df['Unidades']
                df['contas'] = contas
                df['quantidade'] = df['Unidades']

                # Adiciona ao file_list apenas as colunas necessárias
                file_list.append(df[['sku', 'quantidade_itens', 'quantidade_total', 'contas', 'data', 'quantidade']])

            if 'Order' in file and 'all' in file:
                try:
                    df = pd.read_excel(caminho_sub_vendas, header=0)
                    if 'Número de referência SKU' in df.columns:
                        df.rename(columns={'Nº de referência do SKU principal': 'SKU'}, inplace=True)     
                    df['SKU'] = df['SKU'].str.split(' ').explode('SKU')
                    df[['quantidade_itens', 'sku']] = df['SKU'].apply(lambda x: pd.Series(tratar_SKU(x)))
                    # Remove linhas onde 'sku' é NaN ou string vazia
                    df = df[df[['quantidade_itens', 'sku']].notnull() & (df[['quantidade_itens', 'sku']] != '')]
                    df['quantidade_itens'] = pd.to_numeric(df['quantidade_itens'], errors='coerce').fillna(0.0).astype(float)
                    df['Quantidade'] = pd.to_numeric(df['Quantidade'], errors='coerce').fillna(0.0).astype(float)
                    df['quantidade_total'] = df['quantidade_itens'] * df['Quantidade']
                    df['contas'] = contas
                    df['data'] = pd.to_datetime(df['Data de criação do pedido'], errors='coerce').dt.strftime('%Y-%m-%d') 
                    df['quantidade'] = df['Quantidade'] 
                    file_list.append(df[['sku', 'quantidade_itens', 'quantidade_total', 'contas', 'data', 'quantidade']])
                except Exception as e:
                    print(f"Erro ao ler {file}: {e}")
    
    if file_list:
        df_all = pd.concat(file_list, ignore_index=True)
        
        # Agrupa por conta, SKU e data somando os campos numéricos
        df_all = df_all.groupby(['contas', 'sku', 'data']).agg({
            'quantidade_itens': 'sum',
            'quantidade_total': 'sum',
            'quantidade': 'sum'
        }).reset_index()

        # Corrige o tipo de data
        df_all['data'] = pd.to_datetime(df_all['data'])

        df_all.to_excel('vendas.xlsx', index=False)

        # Define o range de datas global (mínimo e máximo considerando todos os SKUs e contas)
        data_inicio_global = df_all['data'].min()
        data_fim_global = df_all['data'].max()
        todas_as_datas = pd.date_range(start=data_inicio_global, end=data_fim_global, freq='D')

        # Lista para os resultados finais
        todos_registros = []

        # Para cada (conta, sku), criar todas as datas no intervalo global
        for (conta, sku), grupo in df_all.groupby(['contas', 'sku']):
            grupo = grupo.set_index('data')
            grupo = grupo.reindex(todas_as_datas, fill_value=0)

            # Recupera data como coluna
            grupo['data'] = grupo.index
            grupo = grupo.reset_index(drop=True)

            # Repreenche as colunas 'contas' e 'sku' (porque as novas datas criadas perdem isso)
            grupo['contas'] = conta
            grupo['sku'] = sku

            todos_registros.append(grupo)

        # Junta todos os grupos novamente
        df_all = pd.concat(todos_registros, ignore_index=True)

        # Se quiser, pode ordenar
        df_all = df_all.sort_values(by=['contas', 'sku', 'data']).reset_index(drop=True)

        # conexão com o banco de dados para enviar para a tabela 'vendas'
        with sqlite3.connect(BANCO_DE_DADOS) as conn:
            cursor = conn.cursor()
            for _, row in df_all.iterrows():
                cursor.execute("""
                    INSERT INTO vendas (sku, quantidade_itens, quantidade_total, contas ,quantidade, data)
                    VALUES (?, ?, ?, ?, ?, ?)
                """, (row['sku'], row['quantidade_itens'], row['quantidade_total'], row['contas'], row['quantidade'], row['data'].strftime('%Y-%m-%d') ))
            conn.commit()
            print("Dados inseridos com sucesso no banco.") 

# Função de interface e responsável por chamar todas as funsões principais, além de gerar os gráficos
def main():
    while True:
        print('Quais das opções abaixo deseja executar?\n'
              '\n1: Atualizar dados das vendas e gerar previsões!'
              '\n2: Atualizar dados do estoque!'
              '\n3: Ver previsão de um SKU e conta específicos!'
              '\n4: Fazer uma previsão geral por Sku!'
              '\n5: Fazer previsão do estoque!'
              '\n6: Fazer uma previsão com estoque e vendas por SKU'
              '\n7: Sair do programa!')
        
        opcao = input('\nSelecione uma das opções:  ')

        if opcao == '1':
            chamar_funcao_banco()
            g_arquivos_vendas()
            gerar_todas_previsoes()
            print("✅ Dados das vendas atualizados e previsões geradas!")

        if opcao == '2':
            g_arquivos_estoque()
            print("✅ Dados do estoque atualizados!")

        elif opcao == '3':
            while True:
                sku_escolhido = input("Digite o SKU que deseja verificar ou digite 'n' para sair: ").strip()
                
                if sku_escolhido.lower() == 'n':
                    break

                conta_escolhida = input("Digite a conta correspondente: ").strip()

                with sqlite3.connect(BANCO_DE_DADOS) as conn:
                    # Buscar previsões
                    df_previsao = pd.read_sql_query("""
                        SELECT data, quantidade_prevista FROM previsão_futura
                        WHERE sku = ? AND conta = ?
                        ORDER BY data
                    """, conn, params=(sku_escolhido, conta_escolhida))

                    # Buscar vendas reais
                    df_vendas = pd.read_sql_query("""
                        SELECT data, quantidade FROM vendas
                        WHERE sku = ? AND contas = ?
                        ORDER BY data
                    """, conn, params=(sku_escolhido, conta_escolhida))

                if df_previsao.empty:
                    print(f"⚠️ Nenhuma previsão encontrada para SKU '{sku_escolhido}' na conta '{conta_escolhida}'.")
                else:
                    print("\n📊 Previsões encontradas:")
                    print(df_previsao[['data', 'quantidade_prevista']])

                    # Prepara os dados
                    df_previsao['data'] = pd.to_datetime(df_previsao['data'])
                    df_vendas['data'] = pd.to_datetime(df_vendas['data'])

                    # Plotar o gráfico
                    plt.figure(figsize=(10, 5))
                    if not df_vendas.empty:
                        plt.plot(df_vendas['data'], df_vendas['quantidade'], label='Vendas reais', marker='o', color='blue')

                    plt.plot(df_previsao['data'], df_previsao['quantidade_prevista'],
                            label='Previsão de vendas', linestyle='--', marker='x', color='orange')

                    plt.title(f"Previsão vs Vendas - SKU: {sku_escolhido} | Conta: {conta_escolhida}")
                    plt.xlabel("Data")
                    plt.ylabel("Quantidade")
                    plt.grid(True)
                    plt.legend()
                    # Limitar número de ticks no eixo X
                    plt.gca().xaxis.set_major_locator(MaxNLocator(nbins=20))
                    plt.gca().xaxis.set_major_formatter(mdates.DateFormatter('%Y-%m-%d'))
                    plt.xticks(rotation=45)
                    plt.tight_layout()
                    plt.show()

                conn.close()

        elif opcao == '4':
            while True:
                sku_escolhido = input("Digite o SKU que deseja verificar ou digite 'n' para sair: ").strip()
                
                if sku_escolhido.lower() == 'n':
                    break

                # Executa a função e captura os dados de retorno
                grupo, vendas_previstas, _ = comparacao_previsao_vendas(sku_escolhido, conta_desejada=None, retornar_dados=True)

                # Se a função retornar None, pula para o próximo loop
                if grupo is None:
                    continue

                # Cria datas futuras para o gráfico
                datas_futuras = pd.date_range(start=grupo['data'].max() + pd.Timedelta(days=1), periods=360)

                # Buscar vendas reais direto do retorno da função
                df_vendas = grupo[['data', 'quantidade']].copy()

                plt.figure(figsize=(10, 5))

                # Plotar vendas reais
                if not df_vendas.empty:
                    plt.plot(df_vendas['data'], df_vendas['quantidade'], label='Vendas reais', marker='o', color='blue')

                # Plotar previsão
                plt.plot(datas_futuras, vendas_previstas, label='Previsão de vendas', linestyle='--', marker='x', color='orange')

                plt.title(f"Previsão vs Vendas - SKU: {sku_escolhido}")
                plt.xlabel("Data")
                plt.ylabel("Quantidade")
                plt.grid(True)
                plt.legend()

                # Limitar número de ticks no eixo X
                plt.gca().xaxis.set_major_locator(MaxNLocator(nbins=20))
                plt.gca().xaxis.set_major_formatter(mdates.DateFormatter('%Y-%m-%d'))

                plt.xticks(rotation=45)
                plt.tight_layout()
                plt.show()

        elif opcao == '5':
            while True:
                sku_escolhido = input("Digite o SKU que deseja verificar ou digite 'n' para sair: ").strip()
                
                with sqlite3.connect(BANCO_DE_DADOS) as conn:
                    # Buscar previsões
                    df_previsao = pd.read_sql_query("""
                        SELECT sku FROM previsão_futura
                    """, conn)

                    # Buscar vendas reais
                    df_vendas = pd.read_sql_query("""
                        SELECT sku FROM vendas                       
                    """, conn)

                if sku_escolhido.lower() == 'n':
                    break

                if sku_escolhido == '':
                    print("SKUS VAZIOS NÃO SÃO ACEITOS, DIGITE UM VALIDO!")
                elif (
                    sku_escolhido not in df_vendas['sku'].values
                    and sku_escolhido not in df_estoque['sku'].values
                    and sku_escolhido not in df_previsao['sku'].values
                    ):
                    print("ESSE SKU NÃO TEM DADOS NECESSÁRIOS PARA UMA BUSCA OU NÃO ESTÁ EM NENHUM DOS BANCOS DE DADOS, TENTE OUTRO!")
                else:
                    # Executa a função e captura os dados de retorno
                    grupo, estoque_previsto, _ = previsao_estoque(sku_escolhido,retornar_dados=True)

                    # Se a função retornar None, pula para o próximo loop
                    if grupo is None:
                        continue

                    # Cria datas futuras para o gráfico
                    datas_futuras = pd.date_range(start=grupo['data'].max() + pd.Timedelta(days=1), periods=360)

                    # Buscar vendas reais direto do retorno da função
                    df_estoque = grupo[['data', 'quantidade_estoque']].copy()

                    plt.figure(figsize=(10, 5))

                    # Plotar vendas reais
                    if not df_estoque.empty:
                        plt.plot(df_estoque['data'], df_estoque['quantidade_estoque'], label='Estoque', marker='o', color='blue')

                    # Plotar previsão
                    plt.plot(datas_futuras, estoque_previsto, label='Previsão de estoque', linestyle='--', marker='x', color='orange')

                    plt.title(f"Previsão vs Estoque - SKU: {sku_escolhido}")
                    plt.xlabel("Data")
                    plt.ylabel("Quantidade")
                    plt.grid(True)
                    plt.legend()

                    # Limitar número de ticks no eixo X
                    plt.gca().xaxis.set_major_locator(MaxNLocator(nbins=20))
                    plt.gca().xaxis.set_major_formatter(mdates.DateFormatter('%Y-%m-%d'))

                    plt.xticks(rotation=45)
                    plt.tight_layout()
                    plt.show()
                    
                    conn.close()

        elif opcao == '6':
            while True:
                with sqlite3.connect(BANCO_DE_DADOS) as conn:
                    # Buscar previsões
                    df_previsao = pd.read_sql_query("""
                        SELECT sku FROM previsão_futura
                    """, conn)

                    # Buscar vendas reais
                    df_vendas = pd.read_sql_query("""
                        SELECT sku FROM vendas                       
                    """, conn)

                sku_escolhido = input("Digite o SKU que deseja verificar ou digite 'n' para sair: ").strip()

                if sku_escolhido.lower() == 'n':
                    break

                if sku_escolhido == '':
                    print("SKUS VAZIOS NÃO SÃO ACEITOS, DIGITE UM VALIDO!")
                elif (
                    sku_escolhido not in df_vendas['sku'].values
                    and sku_escolhido not in df_estoque['sku'].values
                    and sku_escolhido not in df_previsao['sku'].values
                    ):
                    print("ESSE SKU NÃO TEM DADOS NECESSÁRIOS PARA UMA BUSCA OU NÃO ESTÁ EM NENHUM DOS BANCOS DE DADOS, TENTE OUTRO!")
                else:
                    # Executa a função e captura os dados de retorno
                    grupo, vendas_previstas, _ = comparacao_previsao_vendas(sku_escolhido, conta_desejada=None, retornar_dados=True)

                    # Se a função retornar None, pula para o próximo loop
                    if grupo is None:
                        continue

                    # Cria datas futuras para o gráfico
                    datas_futuras = pd.date_range(start=grupo['data'].max() + pd.Timedelta(days=1), periods=360)

                    # Buscar vendas reais direto do retorno da função
                    df_vendas = grupo[['data', 'quantidade']].copy()

                    plt.figure(figsize=(10, 5))

                    # Plotar vendas reais
                    if not df_vendas.empty:
                        plt.plot(df_vendas['data'], df_vendas['quantidade'], label='Vendas reais', marker='o', color='blue')

                    # Plotar previsão
                    plt.plot(datas_futuras, vendas_previstas, label='Previsão de vendas', linestyle='--', marker='x', color='orange')

                    plt.title(f"Previsão vs Vendas - SKU: {sku_escolhido}")
                    plt.xlabel("Data")
                    plt.ylabel("Quantidade")
                    plt.grid(True)
                    plt.legend()

                    # Limitar número de ticks no eixo X
                    plt.gca().xaxis.set_major_locator(MaxNLocator(nbins=20))
                    plt.gca().xaxis.set_major_formatter(mdates.DateFormatter('%Y-%m-%d'))

                    plt.xticks(rotation=45)
                    plt.tight_layout()
                    

                    # Executa a função e captura os dados de retorno
                    grupo, estoque_previsto, _ = previsao_estoque(sku_escolhido,retornar_dados=True)

                    # Se a função retornar None, pula para o próximo loop
                    if grupo is None:
                        continue

                    # Cria datas futuras para o gráfico
                    datas_futuras = pd.date_range(start=grupo['data'].max() + pd.Timedelta(days=1), periods=360)

                    # Buscar vendas reais direto do retorno da função
                    df_estoque = grupo[['data', 'quantidade_estoque']].copy()

                    plt.figure(figsize=(10, 5))

                    # Plotar vendas reais
                    if not df_estoque.empty:
                        plt.plot(df_estoque['data'], df_estoque['quantidade_estoque'], label='Estoque', marker='o', color='blue')

                    # Plotar previsão
                    plt.plot(datas_futuras, estoque_previsto, label='Previsão de estoque', linestyle='--', marker='x', color='orange')

                    plt.title(f"Previsão vs Estoque - SKU: {sku_escolhido}")
                    plt.xlabel("Data")
                    plt.ylabel("Quantidade")
                    plt.grid(True)
                    plt.legend()

                    # Limitar número de ticks no eixo X
                    plt.gca().xaxis.set_major_locator(MaxNLocator(nbins=20))
                    plt.gca().xaxis.set_major_formatter(mdates.DateFormatter('%Y-%m-%d'))

                    plt.xticks(rotation=45)
                    plt.tight_layout()
                    plt.show()
                    
                    conn.close()

        elif opcao == '7':
            print("Encerrando o programa...")
            break

        else:
            print("⚠️ Opção inválida. Tente novamente.")

main()

