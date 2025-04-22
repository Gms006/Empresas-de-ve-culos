import pandas as pd
import xml.etree.ElementTree as ET
import json
import re
import logging

logging.basicConfig(level=logging.INFO, format='%(levelname)s: %(message)s')
log = logging.getLogger(__name__)

# Carregar JSONs
with open('formato_colunas.json', encoding='utf-8') as f:
    FORMATO_COLUNAS = json.load(f)

with open('mapa_campos_extracao.json', encoding='utf-8') as f:
    MAPA_CAMPOS = json.load(f)

with open('regex_extracao.json', encoding='utf-8') as f:
    REGEX_EXTRACAO = json.load(f)

with open('validador_veiculo.json', encoding='utf-8') as f:
    VALIDADORES = json.load(f)

def validar_chassi(chassi):
    return bool(chassi) and re.fullmatch(VALIDADORES["chassi"], chassi)

def validar_placa(placa):
    return bool(placa) and (
        re.fullmatch(VALIDADORES["placa_mercosul"], placa) or
        re.fullmatch(VALIDADORES["placa_antiga"], placa)
    )

def extrair_dados_xml(xml_path):
    try:
        tree = ET.parse(xml_path)
        root = tree.getroot()

        dados = {col: None for col in FORMATO_COLUNAS.keys()}

        for campo, path in MAPA_CAMPOS.items():
            elemento = root.find(path)
            if campo in dados:
                dados[campo] = elemento.text.strip() if elemento is not None and elemento.text else None

        texto_xml = ET.tostring(root, encoding='unicode')
        for campo, padrao in REGEX_EXTRACAO.items():
            match = re.search(padrao, texto_xml, re.IGNORECASE)
            if campo in dados:
                dados[campo] = match.group(1).strip() if match else None

        # Validação
        if not validar_chassi(dados.get("Chassi")):
            dados["Chassi"] = None
        if not validar_placa(dados.get("Placa")):
            dados["Placa"] = None

        return dados

    except Exception as e:
        log.error(f"Erro ao processar {xml_path}: {e}")
        return {col: None for col in FORMATO_COLUNAS.keys()}

def processar_xmls(xml_paths):
    registros = [extrair_dados_xml(p) for p in xml_paths if p.endswith(".xml")]
    df = pd.DataFrame(registros)
    return df
