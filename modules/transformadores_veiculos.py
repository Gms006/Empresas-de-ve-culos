import pandas as pd
import json
import logging
import os

# Configuração de logging
logging.basicConfig(level=logging.INFO, format='%(levelname)s: %(message)s')
log = logging.getLogger(__name__)

# Definir caminho correto para a pasta de configuração
CONFIG_PATH = os.path.join(os.path.dirname(__file__), '..', 'config')

# Carregar regras de classificação de produto
with open(os.path.join(CONFIG_PATH, 'classificacao_produto.json'), encoding='utf-8') as f:
    CLASSIFICACAO_PRODUTO = json.load(f)

BLACKLIST = CLASSIFICACAO_PRODUTO.get("blacklist", [])
KEYWORDS_VEICULO = CLASSIFICACAO_PRODUTO.get("veiculo_keywords", [])

# Função para validar se o produto é um veículo
def verificar_produto_valido(produto):
    if not produto:
        return False
    produto_upper = produto.upper()
    if any(palavra in produto_upper for palavra in BLACKLIST):
        return False
    if any(keyword in produto_upper for keyword in KEYWORDS_VEICULO):
        return True
    return False

# Gerar Estoque Fiscal
def gerar_estoque_fiscal(df_entrada, df_saida):
    """Gera o controle de estoque fiscal a partir das notas de entrada e
    saída.

    A correspondência entre uma nota de entrada e outra de saída é feita
    prioritariamente pelo chassi do veículo. Caso existam múltiplas
    entradas ou saídas para o mesmo chassi elas são pareadas na ordem de
    emissão para evitar cruzamentos duplicados."""

    df_entrada = df_entrada.copy()
    df_saida = df_saida.copy()

    # Priorizar o chassi como chave de rastreamento. Caso ausente, utiliza
    # a placa para manter a compatibilidade com dados mais antigos.
    df_entrada['Chave'] = df_entrada['Chassi'].fillna(df_entrada['Placa']).fillna('')
    df_saida['Chave'] = df_saida['Chassi'].fillna(df_saida['Placa']).fillna('')

    merge_cols = ['Chave']
    if 'Empresa CNPJ' in df_entrada.columns and 'Empresa CNPJ' in df_saida.columns:
        merge_cols.append('Empresa CNPJ')

    # Ordenar pelas datas de emissão para garantir o pareamento correto
    if 'Data Emissão' in df_entrada.columns:
        df_entrada['Data Emissão'] = pd.to_datetime(df_entrada['Data Emissão'], errors='coerce')
    if 'Data Emissão' in df_saida.columns:
        df_saida['Data Emissão'] = pd.to_datetime(df_saida['Data Emissão'], errors='coerce')

    # Criar uma coluna sequencial por chassi/empresa para parear múltiplas
    # entradas e saídas do mesmo veículo.
    df_entrada['seq'] = df_entrada.sort_values('Data Emissão').groupby(merge_cols).cumcount()
    df_saida['seq'] = df_saida.sort_values('Data Emissão').groupby(merge_cols).cumcount()

    df_estoque = pd.merge(
        df_entrada,
        df_saida,
        on=merge_cols + ['seq'],
        how='outer',
        suffixes=('_entrada', '_saida'),
        indicator=True,
    ).drop(columns=['seq'])

    # Classificação do status do veículo
    def classificar_status(merge_flag):
        if merge_flag == 'both':
            return 'Vendido'
        elif merge_flag == 'left_only':
            return 'Em Estoque'
        return 'Erro'

    df_estoque['Situação'] = df_estoque['_merge'].apply(classificar_status)

    # Renomear coluna de data de saída, se existir
    if 'Data Emissão_saida' in df_estoque.columns:
        df_estoque.rename(columns={'Data Emissão_saida': 'Data Saída'}, inplace=True)
    else:
        df_estoque['Data Saída'] = pd.NaT

    df_estoque['Valor Entrada'] = pd.to_numeric(df_estoque.get('Valor Total_entrada'), errors='coerce').fillna(0)
    df_estoque['Valor Venda'] = pd.to_numeric(df_estoque.get('Valor Total_saida'), errors='coerce').fillna(0)
    df_estoque['Lucro'] = df_estoque['Valor Venda'] - df_estoque['Valor Entrada']

    if 'Data Emissão_entrada' in df_estoque.columns:
        df_estoque['Mês Entrada'] = pd.to_datetime(df_estoque['Data Emissão_entrada'], errors='coerce').dt.to_period('M').dt.start_time
    if 'Data Saída' in df_estoque.columns:
        df_estoque['Mês Saída'] = pd.to_datetime(df_estoque['Data Saída'], errors='coerce').dt.to_period('M').dt.start_time

    return df_estoque

# Gerar Alertas de Auditoria
def gerar_alertas_auditoria(df_entrada, df_saida):
    erros = []

    df_entrada = df_entrada.copy()
    df_saida = df_saida.copy()

    df_entrada['Chave'] = df_entrada['Chassi'].fillna(df_entrada['Placa']).fillna('')
    df_saida['Chave'] = df_saida['Chassi'].fillna(df_saida['Placa']).fillna('')

    duplicadas_entrada = df_entrada[df_entrada.duplicated('Chave', keep=False)]
    duplicadas_saida = df_saida[df_saida.duplicated('Chave', keep=False)]

    for _, row in duplicadas_entrada.iterrows():
        if verificar_produto_valido(row.get('Produto', '')):
            erros.append({'Tipo': 'Entrada', 'Nota Fiscal': row.get('Nota Fiscal'), 'Erro': 'DUPLICIDADE_ENTRADA'})

    for _, row in duplicadas_saida.iterrows():
        if verificar_produto_valido(row.get('Produto', '')):
            erros.append({'Tipo': 'Saída', 'Nota Fiscal': row.get('Nota Fiscal'), 'Erro': 'DUPLICIDADE_SAIDA'})

    # Saída sem correspondente na entrada
    entradas_count = df_entrada['Chave'].value_counts()
    saidas_count = df_saida['Chave'].value_counts()

    for chave, qtd_saida in saidas_count.items():
        qtd_entrada = entradas_count.get(chave, 0)
        if qtd_saida > qtd_entrada:
            excedentes = df_saida[df_saida['Chave'] == chave].iloc[qtd_entrada:]
            for _, row in excedentes.iterrows():
                if verificar_produto_valido(row.get('Produto', '')):
                    erros.append({'Tipo': 'Saída', 'Nota Fiscal': row.get('Nota Fiscal'), 'Erro': 'SAIDA_SEM_ENTRADA'})

    return pd.DataFrame(erros)

# Gerar KPIs
def gerar_kpis(df_estoque):
    return {
        "Total Vendido (R$)": df_estoque[df_estoque['Situação'] == 'Vendido']['Valor Venda'].sum(),
        "Lucro Total (R$)": df_estoque['Lucro'].sum(),
        "Estoque Atual (R$)": df_estoque[df_estoque['Situação'] == 'Em Estoque']['Valor Entrada'].sum()
    }

# Gerar Resumo Mensal
def gerar_resumo_mensal(df_estoque):
    df = df_estoque.copy()
    df['Mês Resumo'] = df['Mês Saída'].fillna(df['Mês Entrada'])
    resumo = (
        df.groupby(['Empresa CNPJ', 'Mês Resumo'])
        .agg({'Valor Entrada': 'sum', 'Valor Venda': 'sum', 'Lucro': 'sum'})
        .reset_index()
        .rename(columns={'Mês Resumo': 'Mês'})
    )
    return resumo
