
import pandas as pd
import xml.etree.ElementTree as ET
import json
import re
import os

# Carregar configurações
with open('mapa_campos_extracao.json', encoding='utf-8') as f:
    MAPA_CAMPOS = json.load(f)
with open('regex_extracao.json', encoding='utf-8') as f:
    REGEX_EXTRACAO = json.load(f)
with open('ordem_colunas.json', encoding='utf-8') as f:
    ORDEM_COLUNAS = json.load(f)
with open('formato_colunas.json', encoding='utf-8') as f:
    FORMATO_COLUNAS = json.load(f)
with open('classificacao_produto.json', encoding='utf-8') as f:
    CLASSIFICACAO_PRODUTO = json.load(f)

def extrair_dados_xml(xml_path):
    tree = ET.parse(xml_path)
    root = tree.getroot()
    ns = {'nfe': 'http://www.portalfiscal.inf.br/nfe'}

    dados = {}
    for campo, path in MAPA_CAMPOS.items():
        elemento = root.find(path, ns)
        dados[campo] = elemento.text if elemento is not None else None

    # Aplicar regex adicionais (ex: Chassi, Placa)
    for campo, padrao in REGEX_EXTRACAO.items():
        texto = ET.tostring(root, encoding='unicode')
        match = re.search(padrao, texto)
        dados[campo] = match.group(1) if match else None

    return dados

def processar_arquivos_xml(xml_paths):
    registros = []
    for path in xml_paths:
        if path.endswith(".xml"):
            try:
                registro = extrair_dados_xml(path)
                registros.append(registro)
            except:
                continue

    df = pd.DataFrame(registros)

    # Garantir colunas essenciais
    colunas_obrigatorias = ['Chassi', 'Placa', 'CFOP', 'Data Emissão', 'Destinatário Nome', 'Valor Total', 'Produto', 'Valor Entrada']
    for col in colunas_obrigatorias:
        if col not in df.columns:
            df[col] = None

    # Classificação de Entrada/Saída
    cfops_saida = ["5101", "6101"]
    cliente_final = "Cliente Final"
    df['Tipo Nota'] = df.apply(lambda row: "Saída" if str(row['CFOP']) in cfops_saida or row['Destinatário Nome'] == cliente_final else "Entrada", axis=1)

    df_entrada = df[df['Tipo Nota'] == "Entrada"].copy()
    df_saida = df[df['Tipo Nota'] == "Saída"].copy()

    # Datas
    df_entrada['Data Entrada'] = pd.to_datetime(df_entrada['Data Emissão'], errors='coerce')
    df_saida['Data Saída'] = pd.to_datetime(df_saida['Data Emissão'], errors='coerce')

    return df_entrada, df_saida
