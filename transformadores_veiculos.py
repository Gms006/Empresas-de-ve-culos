
import pandas as pd

def gerar_estoque_fiscal(df_entrada, df_saida):
    df_entrada = df_entrada.copy()
    df_saida = df_saida.copy()

    df_entrada['Chave'] = df_entrada['Chassi'].fillna('').astype(str) + df_entrada['Placa'].fillna('').astype(str)
    df_saida['Chave'] = df_saida['Chassi'].fillna('').astype(str) + df_saida['Placa'].fillna('').astype(str)

    df_saida = df_saida.drop_duplicates(subset='Chave')
    df_estoque = pd.merge(df_entrada, df_saida, on='Chave', how='left', suffixes=('_entrada', '_saida'))

    col_saida = 'Data Saída_saida'
    col_alvo = col_saida if col_saida in df_estoque.columns else 'Data Saída'
    if col_alvo in df_estoque.columns:
        df_estoque['Situação'] = df_estoque[col_alvo].notna().map({True: 'Vendido', False: 'Em Estoque'})
    else:
        df_estoque['Situação'] = "Desconhecida"

    df_estoque['Lucro'] = df_estoque['Valor Venda'].astype(float) - df_estoque['Valor Entrada'].astype(float)

    df_estoque.rename(columns={
        "Data Saída_saida": "Data Saída",
        "Valor Venda_saida": "Valor Venda",
        "Nota Fiscal_saida": "Nota Fiscal Saída"
    }, inplace=True)

    return df_estoque
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
    df = df_estoque[df_estoque['Situação'] == 'Vendido']
    total_vendido = df['Valor Venda'].astype(float).sum()
    lucro_total = df['Lucro'].astype(float).sum()
    estoque_atual = df_estoque[df_estoque['Situação'] == 'Em Estoque']['Valor Entrada'].astype(float).sum()

    return {
        "Total Vendido (R$)": total_vendido,
        "Lucro Total (R$)": lucro_total,
        "Estoque Atual (R$)": estoque_atual
    }

def gerar_resumo_mensal(df_estoque):
    df = df_estoque[df_estoque['Situação'] == 'Vendido'].copy()
    df['Mês'] = pd.to_datetime(df['Data Saída'], errors='coerce').dt.to_period("M").dt.start_time

    resumo = df.groupby('Mês').agg({
        'Valor Entrada': 'sum',
        'Valor Venda': 'sum',
        'Lucro': 'sum'
    }).reset_index()

    return resumo
