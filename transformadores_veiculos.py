
import pandas as pd

def gerar_estoque_fiscal(df_entrada, df_saida):
    df_entrada = df_entrada.copy()
    df_saida = df_saida.copy()

    df_entrada['Chave'] = df_entrada['Chassi'].fillna('').astype(str) + df_entrada['Placa'].fillna('').astype(str)
    df_saida['Chave'] = df_saida['Chassi'].fillna('').astype(str) + df_saida['Placa'].fillna('').astype(str)

    df_saida = df_saida.drop_duplicates(subset='Chave')
    df_estoque = pd.merge(df_entrada, df_saida, on='Chave', how='left', suffixes=('_entrada', '_saida'))

    # Renomear colunas pós-merge
    df_estoque.rename(columns={
        "Data Saída_saida": "Data Saída",
        "Valor Venda_saida": "Valor Venda",
        "Nota Fiscal_saida": "Nota Fiscal Saída"
    }, inplace=True)

    # Situação
    df_estoque['Situação'] = df_estoque['Data Saída'].notna().map({True: 'Vendido', False: 'Em Estoque'})

    # Lucro com proteção
    if 'Valor Venda' in df_estoque.columns and 'Valor Entrada' in df_estoque.columns:
        df_estoque['Lucro'] = df_estoque['Valor Venda'].astype(float).fillna(0) - df_estoque['Valor Entrada'].astype(float).fillna(0)
    else:
        df_estoque['Lucro'] = 0.0

    return df_estoque

def gerar_alertas_auditoria(df_entrada, df_saida):
    erros = []
    df_entrada = df_entrada.copy()
    df_saida = df_saida.copy()

    df_entrada['Chave'] = df_entrada['Chassi'].fillna('').astype(str) + df_entrada['Placa'].fillna('').astype(str)
    df_saida['Chave'] = df_saida['Chassi'].fillna('').astype(str) + df_saida['Placa'].fillna('').astype(str)

    duplicadas_entrada = df_entrada[df_entrada.duplicated('Chave', keep=False)]
    duplicadas_saida = df_saida[df_saida.duplicated('Chave', keep=False)]

    for _, row in duplicadas_entrada.iterrows():
        erros.append({
            'Tipo': 'Entrada',
            'Nota Fiscal': row.get('Nota Fiscal'),
            'Data': row.get('Data Emissão'),
            'Chave': row['Chave'],
            'Erro': 'DUPLICIDADE_ENTRADA',
            'Categoria': 'Crítico'
        })

    for _, row in duplicadas_saida.iterrows():
        erros.append({
            'Tipo': 'Saída',
            'Nota Fiscal': row.get('Nota Fiscal'),
            'Data': row.get('Data Emissão'),
            'Chave': row['Chave'],
            'Erro': 'DUPLICIDADE_SAIDA',
            'Categoria': 'Crítico'
        })

    return pd.DataFrame(erros)

def gerar_kpis(df_estoque):
    if 'Valor Entrada' in df_estoque.columns:
        estoque_atual = df_estoque[df_estoque['Situação'] == 'Em Estoque']['Valor Entrada'].astype(float).sum()
    else:
        estoque_atual = 0.0

    if 'Valor Venda' in df_estoque.columns:
        total_vendido = df_estoque[df_estoque['Situação'] == 'Vendido']['Valor Venda'].astype(float).sum()
    else:
        total_vendido = 0.0

    lucro_total = df_estoque['Lucro'].astype(float).sum() if 'Lucro' in df_estoque.columns else 0.0

    return {
        "Total Vendido (R$)": total_vendido,
        "Lucro Total (R$)": lucro_total,
        "Estoque Atual (R$)": estoque_atual
    }

def gerar_resumo_mensal(df_estoque):
    df = df_estoque[df_estoque['Situação'] == 'Vendido'].copy()
    df['Mês'] = pd.to_datetime(df['Data Saída'], errors='coerce').dt.to_period("M").dt.start_time

    colunas_resumo = {col: 'sum' for col in ['Valor Entrada', 'Valor Venda', 'Lucro'] if col in df.columns}
    resumo = df.groupby('Mês').agg(colunas_resumo).reset_index()

    return resumo
