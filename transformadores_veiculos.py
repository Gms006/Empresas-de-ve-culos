import pandas as pd
import json
import logging

# Configuração de logging
logging.basicConfig(level=logging.INFO, format='%(levelname)s: %(message)s')
log = logging.getLogger(__name__)

# Carregar regras de classificação de produto
with open('classificacao_produto.json', encoding='utf-8') as f:
    CLASSIFICACAO_PRODUTO = json.load(f)

BLACKLIST = CLASSIFICACAO_PRODUTO.get("blacklist", [])
KEYWORDS_VEICULO = CLASSIFICACAO_PRODUTO.get("veiculo_keywords", [])  # Corrigido aqui

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
    df_entrada = df_entrada.copy()
    df_saida = df_saida.copy()

    # Criar chave de identificação
    df_entrada['Chave'] = df_entrada['Chassi'].fillna('') + df_entrada['Placa'].fillna('')
    df_saida['Chave'] = df_saida['Chassi'].fillna('') + df_saida['Placa'].fillna('')

    # Remover duplicados na saída
    df_saida = df_saida.drop_duplicates(subset='Chave')

    # Merge das notas
    df_estoque = pd.merge(df_entrada, df_saida, on='Chave', how='left', suffixes=('_entrada', '_saida'))

    # Definir Situação com base na Data de Emissão da saída
    if 'Data Emissão_saida' in df_estoque.columns:
        df_estoque['Situação'] = df_estoque['Data Emissão_saida'].notna().map({True: 'Vendido', False: 'Em Estoque'})
        df_estoque.rename(columns={'Data Emissão_saida': 'Data Saída'}, inplace=True)
    else:
        df_estoque['Situação'] = 'Em Estoque'
        df_estoque['Data Saída'] = pd.NaT

    # Calcular Lucro
    df_estoque['Valor Entrada'] = pd.to_numeric(df_estoque.get('Valor Total_entrada'), errors='coerce').fillna(0)
    df_estoque['Valor Venda'] = pd.to_numeric(df_estoque.get('Valor Total_saida'), errors='coerce').fillna(0)
    df_estoque['Lucro'] = df_estoque['Valor Venda'] - df_estoque['Valor Entrada']

    return df_estoque

# Gerar Alertas de Auditoria
def gerar_alertas_auditoria(df_entrada, df_saida):
    erros = []

    df_entrada = df_entrada.copy()
    df_saida = df_saida.copy()

    df_entrada['Chave'] = df_entrada['Chassi'].fillna('') + df_entrada['Placa'].fillna('')
    df_saida['Chave'] = df_saida['Chassi'].fillna('') + df_saida['Placa'].fillna('')

    duplicadas_entrada = df_entrada[df_entrada.duplicated('Chave', keep=False)]
    duplicadas_saida = df_saida[df_saida.duplicated('Chave', keep=False)]

    for _, row in duplicadas_entrada.iterrows():
        if verificar_produto_valido(row.get('Produto', '')):
            erros.append({'Tipo': 'Entrada', 'Nota Fiscal': row.get('Nota Fiscal'), 'Erro': 'DUPLICIDADE_ENTRADA'})

    for _, row in duplicadas_saida.iterrows():
        if verificar_produto_valido(row.get('Produto', '')):
            erros.append({'Tipo': 'Saída', 'Nota Fiscal': row.get('Nota Fiscal'), 'Erro': 'DUPLICIDADE_SAIDA'})

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
    df = df_estoque[df_estoque['Situação'] == 'Vendido'].copy()
    df['Mês'] = pd.to_datetime(df['Data Saída'], errors='coerce').dt.to_period("M").dt.start_time
    resumo = df.groupby('Mês').agg({'Valor Entrada': 'sum', 'Valor Venda': 'sum', 'Lucro': 'sum'}).reset_index()
    return resumo
