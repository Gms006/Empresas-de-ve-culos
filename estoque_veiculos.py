
import pandas as pd
import xml.etree.ElementTree as ET
import json
import re

with open('mapa_campos_extracao.json', encoding='utf-8') as f:
    MAPA_CAMPOS = json.load(f)
with open('regex_extracao.json', encoding='utf-8') as f:
    REGEX_EXTRACAO = json.load(f)

def extrair_dados_xml(xml_path):
    try:
        tree = ET.parse(xml_path)
        root = tree.getroot()
        ns = {'nfe': 'http://www.portalfiscal.inf.br/nfe'}

        dados = {}

        # Iterar sobre lista de paths e pegar o primeiro valor encontrado
        for campo, paths in MAPA_CAMPOS.items():
            if isinstance(paths, str):
                paths = [paths]
            valor = None
            for path in paths:
                elemento = root.find(path, ns) or root.find(path)
                if elemento is not None and elemento.text:
                    valor = elemento.text
                    break
            dados[campo] = valor

        # Aplicar regex apenas se o campo ainda estiver vazio
        texto_xml = ET.tostring(root, encoding='unicode')
        for campo, padrao in REGEX_EXTRACAO.items():
            if not dados.get(campo):
                match = re.search(padrao, texto_xml)
                if match:
                    dados[campo] = match.group(1)

        return dados
    except Exception:
        return None

def processar_arquivos_xml(xml_paths):
    registros = [extrair_dados_xml(path) for path in xml_paths if path.endswith(".xml")]
    df = pd.DataFrame(filter(None, registros))

    # Garantir que todas as colunas do JSON estejam no DataFrame
    for col in MAPA_CAMPOS.keys():
        if col not in df.columns:
            df[col] = None

    cfops_saida = ["5101", "5102", "5103", "5949", "6101", "6102", "6108", "6949"]
    cliente_final_ref = "cliente final"

    def classificar_nota(row):
        cfop = str(row['CFOP']).strip() if row['CFOP'] else ""
        destinatario = str(row['Destinatário Nome']).lower() if row['Destinatário Nome'] else ""
        return "Saída" if cfop in cfops_saida or cliente_final_ref in destinatario else "Entrada"

    df['Tipo Nota'] = df.apply(classificar_nota, axis=1)
    df['Data Entrada'] = pd.to_datetime(df['Data Emissão'], errors='coerce')
    df['Data Saída'] = df.apply(lambda row: row['Data Emissão'] if row['Tipo Nota'] == "Saída" else pd.NaT, axis=1)
    df['Data Saída'] = pd.to_datetime(df['Data Saída'], errors='coerce')

    return df[df['Tipo Nota'] == "Entrada"].copy(), df[df['Tipo Nota'] == "Saída"].copy()
