import pandas as pd
import xml.etree.ElementTree as ET
import json
import re
import logging

logging.basicConfig(level=logging.INFO, format='%(levelname)s: %(message)s')
log = logging.getLogger(__name__)

# Carregar Configurações
with open('extracao_config.json', encoding='utf-8') as f:
    CONFIG_EXTRACAO = json.load(f)

with open('layout_colunas.json', encoding='utf-8') as f:
    LAYOUT_COLUNAS = json.load(f)

def validar_chassi(chassi):
    return bool(chassi) and re.fullmatch(CONFIG_EXTRACAO["validadores"]["chassi"], chassi)

def validar_placa(placa):
    return bool(placa) and (
        re.fullmatch(CONFIG_EXTRACAO["validadores"]["placa_mercosul"], placa) or
        re.fullmatch(CONFIG_EXTRACAO["validadores"]["placa_antiga"], placa)
    )

def classificar_tipo_nota(row):
    cfop = str(row.get('CFOP') or "").strip()
    destinatario = str(row.get('Destinatário Nome') or "").lower()
    if cfop in ["5101", "5102", "5103", "5949", "6101", "6102", "6108", "6949"]:
        return "Saída"
    if "cliente final" in destinatario:
        return "Saída"
    return "Entrada"

def extrair_dados_xml(xml_path):
    try:
        tree = ET.parse(xml_path)
        root = tree.getroot()

        dados = {col: None for col in LAYOUT_COLUNAS.keys()}

        for campo, path in CONFIG_EXTRACAO["xpath_campos"].items():
            elemento = root.find(path)
            if campo in dados:
                dados[campo] = elemento.text.strip() if elemento is not None and elemento.text else None

        texto_xml = ET.tostring(root, encoding='unicode')
        for campo, padrao in CONFIG_EXTRACAO["regex_extracao"].items():
            match = re.search(padrao, texto_xml, re.IGNORECASE)
            if campo in dados:
                dados[campo] = match.group(1).strip() if match else None

        if not validar_chassi(dados.get("Chassi")):
            dados["Chassi"] = None
        if not validar_placa(dados.get("Placa")):
            dados["Placa"] = None

        return dados

    except Exception as e:
        log.error(f"Erro ao processar {xml_path}: {e}")
        return {col: None for col in LAYOUT_COLUNAS.keys()}

def processar_xmls(xml_paths):
    registros = [extrair_dados_xml(p) for p in xml_paths if p.endswith(".xml")]
    df = pd.DataFrame(registros)
    df['Tipo Nota'] = df.apply(classificar_tipo_nota, axis=1)
    return df
