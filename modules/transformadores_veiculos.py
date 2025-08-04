import pandas as pd
import logging
import re

# Configuração de logging
logging.basicConfig(level=logging.INFO, format='%(levelname)s: %(message)s')
log = logging.getLogger(__name__)

# Gerar Estoque Fiscal
def _limpar_chave(valor: str) -> str:
    """Remove caracteres não alfanuméricos e aplica caixa alta."""
    if valor is None:
        return ""
    return re.sub(r"\W", "", str(valor)).upper()


def gerar_estoque_fiscal(df_entrada, df_saida):
    df_entrada = df_entrada.copy()
    df_saida = df_saida.copy()

    if 'Tipo Produto' in df_entrada.columns:
        df_entrada = df_entrada[df_entrada['Tipo Produto'] == 'Veículo']
    if 'Tipo Produto' in df_saida.columns:
        df_saida = df_saida[df_saida['Tipo Produto'] == 'Veículo']

    # Manter apenas itens classificados como Veículo
    if "Tipo Produto" in df_entrada.columns:
        df_entrada = df_entrada[df_entrada["Tipo Produto"] == "Veículo"].copy()
    if "Tipo Produto" in df_saida.columns:
        df_saida = df_saida[df_saida["Tipo Produto"] == "Veículo"].copy()

    # Utilizar o chassi como chave de rastreamento principal. Caso o chassi não
    # esteja disponível, utiliza-se a placa apenas como apoio.
    df_entrada['Chave'] = df_entrada['Chassi'].apply(_limpar_chave)
    df_saida['Chave'] = df_saida['Chassi'].apply(_limpar_chave)

    df_entrada.loc[df_entrada['Chave'] == '', 'Chave'] = (
        df_entrada['Placa'].apply(_limpar_chave)
    )
    df_saida.loc[df_saida['Chave'] == '', 'Chave'] = (
        df_saida['Placa'].apply(_limpar_chave)
    )

    merge_cols = ['Chave']
    if 'Empresa CNPJ' in df_entrada.columns and 'Empresa CNPJ' in df_saida.columns:
        merge_cols.append('Empresa CNPJ')

    # Remover duplicidades explícitas de saída para evitar múltiplas associações
    df_saida = df_saida.drop_duplicates(subset=merge_cols)

    # Usar junção externa para identificar saídas sem entradas
    df_estoque = pd.merge(
        df_entrada,
        df_saida,
        on=merge_cols,
        how='outer',
        suffixes=('_entrada', '_saida'),
        indicator=True,
    )

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

    def _obter_valor(df, prefixo):
        col_total = f'Valor Total_{prefixo}'
        col_item = f'Valor Item_{prefixo}'
        if col_total in df.columns:
            return pd.to_numeric(df[col_total], errors='coerce')
        if col_item in df.columns:
            return pd.to_numeric(df[col_item], errors='coerce')
        return pd.Series([0] * len(df), index=df.index)

    df_estoque['Valor Entrada'] = _obter_valor(df_estoque, 'entrada').fillna(0)
    df_estoque['Valor Venda'] = _obter_valor(df_estoque, 'saida').fillna(0)
    df_estoque['Lucro'] = df_estoque['Valor Venda'] - df_estoque['Valor Entrada']

    if 'Data Emissão_entrada' in df_estoque.columns:
        df_estoque['Mês Entrada'] = pd.to_datetime(
            df_estoque['Data Emissão_entrada'], errors='coerce'
        ).dt.to_period('M').dt.start_time
    if 'Data Saída' in df_estoque.columns:
        df_estoque['Mês Saída'] = pd.to_datetime(
            df_estoque['Data Saída'], errors='coerce'
        ).dt.to_period('M').dt.start_time

    # Coluna base para filtros
    df_estoque['Data Base'] = df_estoque['Data Saída'].combine_first(
        df_estoque.get('Data Emissão_entrada')
    )
    df_estoque['Mês Base'] = pd.to_datetime(
        df_estoque['Data Base'], errors='coerce'
    ).dt.to_period('M').dt.start_time

    return df_estoque

# Gerar Alertas de Auditoria
def gerar_alertas_auditoria(df_entrada, df_saida):
    erros = []

    df_entrada = df_entrada.copy()
    df_saida = df_saida.copy()

    df_entrada['Chave'] = df_entrada['Chassi'].apply(_limpar_chave)
    df_saida['Chave'] = df_saida['Chassi'].apply(_limpar_chave)

    df_entrada.loc[df_entrada['Chave'] == '', 'Chave'] = (
        df_entrada['Placa'].apply(_limpar_chave)
    )
    df_saida.loc[df_saida['Chave'] == '', 'Chave'] = (
        df_saida['Placa'].apply(_limpar_chave)
    )

    duplicadas_entrada = df_entrada[df_entrada.duplicated('Chave', keep=False)]
    duplicadas_saida = df_saida[df_saida.duplicated('Chave', keep=False)]

    for _, row in duplicadas_entrada.iterrows():
        if row.get('Chassi'):
            erros.append({'Tipo': 'Entrada', 'Nota Fiscal': row.get('Nota Fiscal'), 'Erro': 'DUPLICIDADE_ENTRADA'})

    for _, row in duplicadas_saida.iterrows():
        if row.get('Chassi'):
            erros.append({'Tipo': 'Saída', 'Nota Fiscal': row.get('Nota Fiscal'), 'Erro': 'DUPLICIDADE_SAIDA'})

    # Saída sem correspondente na entrada
    chaves_entrada = set(df_entrada['Chave'])
    saidas_sem_entrada = df_saida[~df_saida['Chave'].isin(chaves_entrada)]

    for _, row in saidas_sem_entrada.iterrows():
        if row.get('Chassi'):
            erros.append({'Tipo': 'Saída', 'Nota Fiscal': row.get('Nota Fiscal'), 'Erro': 'SAIDA_SEM_ENTRADA'})

    return pd.DataFrame(erros)

# Gerar KPIs
def gerar_kpis(df_estoque):
    """Calcula indicadores de desempenho financeiros e fiscais."""

    vendidos = df_estoque[df_estoque["Situação"] == "Vendido"].copy()
    estoque = df_estoque[df_estoque["Situação"] == "Em Estoque"].copy()

    icms_debito = (
        pd.to_numeric(vendidos.get("ICMS Valor_saida"), errors="coerce")
        .fillna(0)
        .sum()
    )
    icms_credito = (
        pd.to_numeric(vendidos.get("ICMS Valor_entrada"), errors="coerce")
        .fillna(0)
        .sum()
    )
    lucro_liquido = (vendidos["Lucro"].sum() - icms_debito + icms_credito)

    return {
        "Total Vendido (R$)": vendidos["Valor Venda"].sum(),
        "Lucro Líquido (R$)": lucro_liquido,
        "ICMS Débito (R$)": icms_debito,
        "ICMS Crédito (R$)": icms_credito,
        "ICMS Apurado (R$)": icms_debito - icms_credito,
        "Estoque Atual (R$)": estoque["Valor Entrada"].sum(),
    }

# Gerar Resumo Mensal
def gerar_resumo_mensal(df_estoque):
    """Gera resumo financeiro mensal com lucros e ICMS."""

    df = df_estoque.copy()
    base_col = "Mês Base" if "Mês Base" in df.columns else "Mês Saída"
    entrada_vals = df.get("Mês Entrada")
    df["Mês Resumo"] = df[base_col].fillna(
        entrada_vals if entrada_vals is not None else pd.NaT
    )

    group_cols = ["Mês Resumo"]
    index_cols = ["Mês"]
    if "Empresa CNPJ" in df.columns:
        group_cols.insert(0, "Empresa CNPJ")
        index_cols.insert(0, "Empresa CNPJ")

    df["ICMS Débito"] = pd.to_numeric(
        df.get("ICMS Valor_saida"), errors="coerce"
    ).fillna(0)
    df["ICMS Crédito"] = pd.to_numeric(
        df.get("ICMS Valor_entrada"), errors="coerce"
    ).fillna(0)

    resumo = (
        df.groupby(group_cols)
        .agg(
            {
                "Valor Entrada": "sum",
                "Valor Venda": "sum",
                "Lucro": "sum",
                "ICMS Débito": "sum",
                "ICMS Crédito": "sum",
            }
        )
        .reset_index()
        .rename(
            columns={
                "Mês Resumo": "Mês",
                "Valor Entrada": "Total Entradas",
                "Valor Venda": "Total Saídas",
                "Lucro": "Lucro Bruto",
            }
        )
    )

    resumo["Lucro Líquido"] = resumo["Lucro Bruto"] - (
        resumo["ICMS Débito"] - resumo["ICMS Crédito"]
    )
    estoque_vals = (
        df[df["Situação"] == "Em Estoque"].groupby(group_cols)["Valor Entrada"].sum()
    )
    resumo["Saldo Estoque"] = estoque_vals.reindex(
        resumo.set_index(index_cols).index, fill_value=0
    ).values

    return resumo
