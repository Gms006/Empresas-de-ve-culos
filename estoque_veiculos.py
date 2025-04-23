import pandas as pd
import xml.etree.ElementTree as ET
import json
import re
import logging

# Configuração de Logs
logging.basicConfig(level=logging.INFO, format='%(levelname)s: %(message)s')
log = logging.getLogger(__name__)

# Carregar Configurações
with open('config/extracao_config.json', encoding='utf-8') as f:
    CONFIG = json.load(f)

XPATH_CAMPOS = CONFIG["xpath_campos"]
REGEX_EXTRACAO = CONFIG["regex_extracao"]
VALIDADORES = CONFIG["validadores"]

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
        dados = {campo: None for campo in XPATH_CAMPOS.keys()}
        dados.update({campo: None for campo in REGEX_EXTRACAO.keys()})

        # Extração via XPath
        for campo, path in XPATH_CAMPOS.items():
            elemento = root.find(path)
            if elemento is not None and elemento.text:
                dados[campo] = elemento.text.strip()

        # Extração via Regex
        texto_xml = ET.tostring(root, encoding='unicode')
        for campo, padroes in REGEX_EXTRACAO.items():
            for padrao in padroes:
                match = re.search(padrao, texto_xml, re.IGNORECASE)
                if match:
                    dados[campo] = match.group(1).strip()
                    break

        # Validação
        if not validar_chassi(dados.get("Chassi")):
            dados["Chassi"] = None
        if not validar_placa(dados.get("Placa")):
            dados["Placa"] = None

        return dados

    except Exception as e:
        log.error(f"Erro ao processar {xml_path}: {e}")
        return {campo: None for campo in list(XPATH_CAMPOS.keys()) + list(REGEX_EXTRACAO.keys())}

def classificar_tipo(row):
    cfop_saida = ["5101", "5102", "5103", "5949", "6101", "6102", "6108", "6949"]
    cfop = str(row.get('CFOP') or "").strip()
    destinatario = str(row.get('Destinatário Nome') or "").lower()

    if cfop in cfop_saida:
        return "Saída"
    if "cliente final" in destinatario:
        return "Saída"
    if cfop:
        return "Entrada"
    return "Não Classificado"

def processar_xmls(xml_paths):
    registros = [extrair_dados_xml(p) for p in xml_paths if p.endswith(".xml")]
    df = pd.DataFrame(registros)
    if not df.empty:
        df['Tipo Nota'] = df.apply(classificar_tipo, axis=1)
    return df
