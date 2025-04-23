
import pandas as pd
import xml.etree.ElementTree as ET
import json
import re
import logging
import os

# Configuração de Logs
logging.basicConfig(level=logging.INFO, format='%(levelname)s: %(message)s')
log = logging.getLogger(__name__)

CONFIG_PATH = os.path.join(os.path.dirname(__file__), '..', 'config')

with open(os.path.join(CONFIG_PATH, 'extracao_config.json'), encoding='utf-8') as f:
    CONFIG_EXTRACAO = json.load(f)

with open(os.path.join(CONFIG_PATH, 'layout_colunas.json'), encoding='utf-8') as f:
    LAYOUT_COLUNAS = json.load(f)

# Validações
def validar_chassi(chassi):
    return bool(chassi) and re.fullmatch(CONFIG_EXTRACAO["validadores"]["chassi"], chassi)

def validar_placa(placa):
    return bool(placa) and (
        re.fullmatch(CONFIG_EXTRACAO["validadores"]["placa_mercosul"], placa) or
        re.fullmatch(CONFIG_EXTRACAO["validadores"]["placa_antiga"], placa)
    )

# Classificação Entrada/Saída
def classificar_tipo_nota(emitente_cnpj, destinatario_cnpj, cnpj_empresa):
    emitente = str(emitente_cnpj or "").replace('.', '').replace('/', '').replace('-', '')
    destinatario = str(destinatario_cnpj or "").replace('.', '').replace('/', '').replace('-', '')

    if destinatario == cnpj_empresa:
        return "Entrada"
    else:
        return "Saída"

# Classificação Veículo x Consumo
def classificar_produto(row):
    if row.get('Chassi'):
        return "Veículo"
    if row.get('Placa'):
        return "Veículo"
    return "Consumo"

# Extração por Produto com Garantia de Colunas
def extrair_dados_xml(xml_path):
    try:
        tree = ET.parse(xml_path)
        root = tree.getroot()
        ns = {'nfe': 'http://www.portalfiscal.inf.br/nfe'}

        emitente_cnpj = root.findtext('.//nfe:emit/nfe:CNPJ', namespaces=ns) or 'Não informado'
        destinatario_cnpj = root.findtext('.//nfe:dest/nfe:CNPJ', namespaces=ns) or 'Não informado'
        cfop = root.findtext('.//nfe:det/nfe:prod/nfe:CFOP', namespaces=ns)
        data_emissao = root.findtext('.//nfe:ide/nfe:dhEmi', namespaces=ns)
        emitente_nome = root.findtext('.//nfe:emit/nfe:xNome', namespaces=ns)
        destinatario_nome = root.findtext('.//nfe:dest/nfe:xNome', namespaces=ns)
        valor_total = root.findtext('.//nfe:total/nfe:ICMSTot/nfe:vNF', namespaces=ns)

        registros = []

        for item in root.findall('.//nfe:det', ns):
            dados = {col: None for col in LAYOUT_COLUNAS.keys()}

            dados['CFOP'] = cfop
            dados['Data Emissão'] = data_emissao
            dados['Emitente Nome'] = emitente_nome
            dados['Emitente CNPJ'] = emitente_cnpj
            dados['Destinatario Nome'] = destinatario_nome
            dados['Destinatario CNPJ'] = destinatario_cnpj
            dados['Valor Total'] = valor_total

            xProd = item.findtext('.//nfe:prod/nfe:xProd', namespaces=ns) or ""
            infAdProd = item.findtext('.//nfe:prod/nfe:infAdProd', namespaces=ns) or ""
            produto_completo = f"{xProd} {infAdProd}".strip()

            dados['Produto'] = xProd

            for campo, padrao in CONFIG_EXTRACAO["regex_extracao"].items():
                if campo == "Ano Modelo":
                    anos = re.search(padrao, produto_completo, re.IGNORECASE)
                    if anos:
                        dados["Ano Fabricação"] = anos.group(1)
                        dados["Ano Modelo"] = anos.group(2)
                else:
                    match = re.search(padrao, produto_completo, re.IGNORECASE)
                    if campo in dados and not dados[campo]:
                        dados[campo] = match.group(1).strip() if match else None

            if not validar_chassi(dados.get("Chassi")):
                dados["Chassi"] = None
            if not validar_placa(dados.get("Placa")):
                dados["Placa"] = None

            registros.append(dados)

        return registros

    except Exception as e:
        log.error(f"Erro ao processar {xml_path}: {e}")
        return []

# Processar XMLs com segurança
def processar_xmls(xml_paths, cnpj_empresa):
    todos_registros = []
    for p in xml_paths:
        registros = extrair_dados_xml(p)
        todos_registros.extend(registros)

    df = pd.DataFrame(todos_registros)

    # Garantir que as colunas existam
    if 'Emitente CNPJ' not in df.columns:
        df['Emitente CNPJ'] = 'Não informado'
    if 'Destinatario CNPJ' not in df.columns:
        df['Destinatario CNPJ'] = 'Não informado'

    df['Tipo Nota'] = df.apply(lambda row: classificar_tipo_nota(row['Emitente CNPJ'], row['Destinatario CNPJ'], cnpj_empresa), axis=1)
    df['Tipo Produto'] = df.apply(classificar_produto, axis=1)

    return df
