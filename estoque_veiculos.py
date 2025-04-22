
import pandas as pd
import xml.etree.ElementTree as ET
import json
import re

with open('mapa_campos_extracao.json', encoding='utf-8') as f:
    MAPA_CAMPOS = json.load(f)
with open('regex_extracao.json', encoding='utf-8') as f:
    REGEX_EXTRACAO = json.load(f)

def extrair_dados_xml(xml_path):
    tree = ET.parse(xml_path)
    root = tree.getroot()
    ns = {'nfe': 'http://www.portalfiscal.inf.br/nfe'}

    dados = {}
    for campo, path in MAPA_CAMPOS.items():
        elemento = root.find(path, ns)
        dados[campo] = elemento.text if elemento is not None else None

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

    colunas_obrigatorias = ['Chassi', 'Placa', 'CFOP', 'Data Emissão', 'Destinatário Nome', 'Valor Total', 'Produto', 'Valor Entrada']
    for col in colunas_obrigatorias:
        if col not in df.columns:
            df[col] = None

    # Classificação
    cfops_saida = ["5101", "5102", "5103", "5949", "6101", "6102", "6108", "6949"]
    cliente_final_ref = "cliente final"

    def classificar_nota(row):
        cfop = str(row['CFOP']).strip()
        destinatario = str(row['Destinatário Nome']).lower()
        if cfop in cfops_saida or cliente_final_ref in destinatario:
            return "Saída"
        return "Entrada"

    df['Tipo Nota'] = df.apply(classificar_nota, axis=1)

    df['Data Entrada'] = pd.to_datetime(df['Data Emissão'], errors='coerce')
    df['Data Saída'] = df.apply(lambda row: row['Data Entrada'] if row['Tipo Nota'] == "Saída" else pd.NaT, axis=1)

    df_entrada = df[df['Tipo Nota'] == "Entrada"].copy()
    df_saida = df[df['Tipo Nota'] == "Saída"].copy()

    return df_entrada, df_saida
