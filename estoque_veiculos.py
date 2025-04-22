
import pandas as pd
import xml.etree.ElementTree as ET
import json
import re

with open('mapa_campos_extracao.json', encoding='utf-8') as f:
    MAPA_CAMPOS = json.load(f)
with open('regex_extracao.json', encoding='utf-8') as f:
    REGEX_EXTRACAO = json.load(f)

def extrair_dados_xml(xml_path, erros_resumo):
    try:
        tree = ET.parse(xml_path)
        root = tree.getroot()
        ns = {'nfe': 'http://www.portalfiscal.inf.br/nfe'}

        dados = {}

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
            if not valor:
                erros_resumo[campo] = erros_resumo.get(campo, 0) + 1

        texto_xml = ET.tostring(root, encoding='unicode')
        for campo, padrao in REGEX_EXTRACAO.items():
            if not dados.get(campo):
                match = re.search(padrao, texto_xml)
                if match:
                    dados[campo] = match.group(1)
                else:
                    erros_resumo[campo] = erros_resumo.get(campo, 0) + 1

        return dados
    except Exception as e:
        erros_resumo['Erros Críticos'] = erros_resumo.get('Erros Críticos', 0) + 1
        return None

def processar_arquivos_xml(xml_paths):
    erros_resumo = {}
    registros = [extrair_dados_xml(path, erros_resumo) for path in xml_paths if path.endswith(".xml")]
    registros_validos = list(filter(None, registros))

    df = pd.DataFrame(registros_validos)

    for col in MAPA_CAMPOS.keys():
        if col not in df.columns:
            df[col] = None

    cfops_saida = ["5101", "5102", "5103", "5949", "6101", "6102", "6108", "6949"]
    cliente_final_ref = "cliente final"

    if not df.empty:
        df['Tipo Nota'] = df.apply(lambda row: "Saída" if str(row['CFOP']).strip() in cfops_saida or cliente_final_ref in str(row['Destinatário Nome']).lower() else "Entrada", axis=1)
        df['Data Entrada'] = pd.to_datetime(df['Data Emissão'], errors='coerce')
        df['Data Saída'] = df.apply(lambda row: row['Data Emissão'] if row['Tipo Nota'] == "Saída" else pd.NaT, axis=1)
        df['Data Saída'] = pd.to_datetime(df['Data Saída'], errors='coerce')
    else:
        df['Tipo Nota'] = None  # Garantir que a coluna exista

    entradas = df[df['Tipo Nota'] == "Entrada"].shape[0] if 'Tipo Nota' in df.columns else 0
    saidas = df[df['Tipo Nota'] == "Saída"].shape[0] if 'Tipo Nota' in df.columns else 0

    print(f"📊 RESUMO FINAL")
    print(f"- XMLs processados: {len(xml_paths)}")
    print(f"- Registros válidos: {len(registros_validos)}")
    print(f"- Entradas: {entradas}, Saídas: {saidas}")
    print(f"- Campos não encontrados:")
    for campo, qtd in erros_resumo.items():
        print(f"  • {campo}: {qtd} vezes")

    return df[df['Tipo Nota'] == "Entrada"].copy(), df[df['Tipo Nota'] == "Saída"].copy()
