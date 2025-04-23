import pandas as pd
import xml.etree.ElementTree as ET
import json
import re
import logging
import os

# Configuração de Logs
logging.basicConfig(level=logging.INFO, format='%(levelname)s: %(message)s')
log = logging.getLogger(__name__)

# Caminho para a pasta de configurações
CONFIG_PATH = os.path.join(os.path.dirname(__file__), '..', 'config')

# Carregar Configurações
with open(os.path.join(CONFIG_PATH, 'extracao_config.json'), encoding='utf-8') as f:
    CONFIG_EXTRACAO = json.load(f)

with open(os.path.join(CONFIG_PATH, 'layout_colunas.json'), encoding='utf-8') as f:
    LAYOUT_COLUNAS = json.load(f)

# Funções de Validação
def validar_chassi(chassi):
    return bool(chassi) and re.fullmatch(CONFIG_EXTRACAO["validadores"]["chassi"], chassi)

def validar_placa(placa):
    return bool(placa) and (
        re.fullmatch(CONFIG_EXTRACAO["validadores"]["placa_mercosul"], placa) or
        re.fullmatch(CONFIG_EXTRACAO["validadores"]["placa_antiga"], placa)
    )

# 🚨 Classificação SEM "Outros"
def classificar_tipo_nota(row, cnpj_empresa):
    emitente = str(row.get('Emitente CNPJ') or "").replace('.', '').replace('/', '').replace('-', '')
    destinatario = str(row.get('Destinatário CNPJ') or "").replace('.', '').replace('/', '').replace('-', '')

    if destinatario == cnpj_empresa:
        return "Entrada"
    else:
        return "Saída"

# Função principal de extração
def extrair_dados_xml(xml_path):
    try:
        tree = ET.parse(xml_path)
        root = tree.getroot()

        ns = {'nfe': 'http://www.portalfiscal.inf.br/nfe'}
        dados = {col: None for col in LAYOUT_COLUNAS.keys()}

        # Extração via XPath
        for campo, path in CONFIG_EXTRACAO["xpath_campos"].items():
            elemento = root.find(path, ns)
            if campo in dados:
                dados[campo] = elemento.text.strip() if elemento is not None and elemento.text else None

        # Extrair tpNF se necessário
        tpNF_element = root.find('.//nfe:ide/nfe:tpNF', ns)
        dados['tpNF'] = tpNF_element.text.strip() if tpNF_element is not None and tpNF_element.text else None

        # Regex para campos adicionais
        texto_xml = ET.tostring(root, encoding='unicode')
        anos = re.search(CONFIG_EXTRACAO["regex_extracao"]["Ano Modelo"], texto_xml, re.IGNORECASE)
        if anos:
            dados["Ano Fabricação"] = anos.group(1)
            dados["Ano Modelo"] = anos.group(2)

        for campo, padrao in CONFIG_EXTRACAO["regex_extracao"].items():
            if campo == "Ano Modelo":
                continue
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

# Processar XMLs com classificação correta
def processar_xmls(xml_paths, cnpj_empresa):
    registros = [extrair_dados_xml(p) for p in xml_paths if p.endswith(".xml")]
    df = pd.DataFrame(registros)
    df['Tipo Nota'] = df.apply(lambda row: classificar_tipo_nota(row, cnpj_empresa), axis=1)
    return df
