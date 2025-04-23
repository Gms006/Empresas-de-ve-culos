import xml.etree.ElementTree as ET
import re
import json
import pandas as pd
import logging

# Configuração do logger
logging.basicConfig(level=logging.INFO)
log = logging.getLogger(__name__)

# Carregar configurações de extração
with open("extracao_config.json", encoding="utf-8") as f:
    config = json.load(f)

XPATH_CAMPOS = config["xpath_campos"]
REGEX_EXTRACAO = config["regex_extracao"]
VALIDADORES = config["validadores"]

# Registro do namespace 'nfe'
namespaces = {'nfe': 'http://www.portalfiscal.inf.br/nfe'}

def validar_chassi(chassi):
    if not chassi:
        return False
    return bool(re.match(VALIDADORES["chassi"], chassi))

def validar_placa(placa):
    if not placa:
        return False
    return bool(
        re.match(VALIDADORES["placa_mercosul"], placa)
        or re.match(VALIDADORES["placa_antiga"], placa)
    )

def extrair_dados_xml(xml_path):
    try:
        tree = ET.parse(xml_path)
        root = tree.getroot()
        dados = {campo: None for campo in XPATH_CAMPOS.keys()}
        dados.update({campo: None for campo in REGEX_EXTRACAO.keys()})

        # Extração via XPath com namespace
        for campo, path in XPATH_CAMPOS.items():
            elemento = root.find(path, namespaces)
            if elemento is not None and elemento.text:
                dados[campo] = elemento.text.strip()

        # Extração via Regex
        texto_xml = ET.tostring(root, encoding="unicode")
        for campo, padrao in REGEX_EXTRACAO.items():
            match = re.search(padrao, texto_xml, re.IGNORECASE)
            if match:
                dados[campo] = match.group(1).strip()

        # Validação
        if not validar_chassi(dados.get("Chassi")):
            dados["Chassi"] = None
        if not validar_placa(dados.get("Placa")):
            dados["Placa"] = None

        return dados

    except Exception as e:
        log.error(f"Erro ao processar {xml_path}: {e}")
        return {campo: None for campo in list(XPATH_CAMPOS.keys()) + list(REGEX_EXTRACAO.keys())}

def processar_xmls(lista_caminhos):
    registros = []
    for caminho in lista_caminhos:
        dados = extrair_dados_xml(caminho)
        registros.append(dados)
    return pd.DataFrame(registros)
