
import pandas as pd
import re
import json

with open('mapa_campos_extracao.json', encoding='utf-8') as f:
    MAPA_CAMPOS = json.load(f)
with open('classificacao_produto.json', encoding='utf-8') as f:
    CLASSIFICACAO_PRODUTO = json.load(f)

def processar_arquivos_xml(xml_paths):
    dados = []
    for path in xml_paths:
        # Simulação da extração com base no MAPA_CAMPOS
        dados.append({
            "CFOP": "5101",  # Exemplo
            "Destinatário Nome": "Cliente Final",
            "Data Emissão": "2024-05-10",
            "Valor Total": 50000,
            "Produto": "Veículo XYZ"
        })
    df = pd.DataFrame(dados)

    cfops_saida = ["5101", "6101"]
    cliente_final = "Cliente Final"

    df['Tipo Nota'] = df.apply(lambda row: "Saída" if row['CFOP'] in cfops_saida or row['Destinatário Nome'] == cliente_final else "Entrada", axis=1)

    df_entrada = df[df['Tipo Nota'] == "Entrada"].copy()
    df_saida = df[df['Tipo Nota'] == "Saída"].copy()

    # Garantir Data Entrada e Data Saída
    if 'Data Emissão' in df_entrada.columns:
        df_entrada['Data Entrada'] = pd.to_datetime(df_entrada['Data Emissão'], errors='coerce')
    else:
        df_entrada['Data Entrada'] = pd.NaT

    if 'Data Emissão' in df_saida.columns:
        df_saida['Data Saída'] = pd.to_datetime(df_saida['Data Emissão'], errors='coerce')
    else:
        df_saida['Data Saída'] = pd.NaT

    return df_entrada, df_saida
