
import pandas as pd
import xml.etree.ElementTree as ET
import json
import re
from collections import Counter

with open('mapa_campos_extracao.json', encoding='utf-8') as f:
    MAPA_CAMPOS = json.load(f)
with open('regex_extracao.json', encoding='utf-8') as f:
    REGEX_EXTRACAO = json.load(f)

def extrair_dados_xml(xml_path, contador_falhas, erros_criticos):
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
                contador_falhas[campo] += 1

        texto_xml = ET.tostring(root, encoding='unicode')
        for campo, padrao in REGEX_EXTRACAO.items():
            match = re.search(padrao, texto_xml)
            if match:
                dados[campo] = match.group(1)
            else:
                contador_falhas[campo] += 1

        return dados
    except Exception as e:
        erros_criticos.append(f"{xml_path} -> {str(e)}")
        return None

def processar_arquivos_xml(xml_paths):
    open("log_extracao.txt", "w").close()

    registros = []
    contador_falhas = Counter()
    erros_criticos = []

    for path in xml_paths:
        if path.endswith(".xml"):
            registro = extrair_dados_xml(path, contador_falhas, erros_criticos)
            if registro:
                registros.append(registro)

    df = pd.DataFrame(registros)

    colunas_obrigatorias = ['Chassi', 'Placa', 'CFOP', 'Data Emissão', 'Destinatário Nome', 'Valor Total', 'Produto', 'Valor Entrada']
    for col in colunas_obrigatorias:
        if col not in df.columns:
            df[col] = None

    cfops_saida = ["5101", "5102", "5103", "5949", "6101", "6102", "6108", "6949"]
    cliente_final_ref = "cliente final"

    def classificar_nota(row):
        cfop = str(row['CFOP']).strip() if row['CFOP'] else ""
        destinatario = str(row['Destinatário Nome']).lower() if row['Destinatário Nome'] else ""
        if cfop in cfops_saida or cliente_final_ref in destinatario:
            return "Saída"
        return "Entrada"

    df['Tipo Nota'] = df.apply(classificar_nota, axis=1)

    entradas = df[df['Tipo Nota'] == "Entrada"].shape[0]
    saidas = df[df['Tipo Nota'] == "Saída"].shape[0]

    # Gerar LOG RESUMIDO
    with open("log_extracao.txt", "a", encoding="utf-8") as log:
        log.write(f"📊 RESUMO DA EXTRAÇÃO\n")
        log.write(f"- XMLs processados: {len(xml_paths)}\n")
        log.write(f"- Sucesso: {len(registros)}\n")
        log.write(f"- Erros críticos: {len(erros_criticos)}\n")
        log.write(f"- Notas de Entrada: {entradas}\n")
        log.write(f"- Notas de Saída: {saidas}\n\n")

        if contador_falhas:
            log.write("🚨 Campos mais ausentes:\n")
            for campo, qtd in contador_falhas.most_common():
                log.write(f"- {campo}: {qtd} falhas\n")

        if erros_criticos:
            log.write("\n❌ Erros críticos detectados:\n")
            for erro in erros_criticos[:5]:
                log.write(f"{erro}\n")
            if len(erros_criticos) > 5:
                log.write(f"... e mais {len(erros_criticos) - 5} erros\n")

    df['Data Entrada'] = pd.to_datetime(df['Data Emissão'], errors='coerce')
    df['Data Saída'] = df.apply(lambda row: row['Data Emissão'] if row['Tipo Nota'] == "Saída" else pd.NaT, axis=1)
    df['Data Saída'] = pd.to_datetime(df['Data Saída'], errors='coerce')

    df_entrada = df[df['Tipo Nota'] == "Entrada"].copy()
    df_saida = df[df['Tipo Nota'] == "Saída"].copy()

    return df_entrada, df_saida
