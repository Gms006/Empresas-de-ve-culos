modules/estoque_veiculos.py
```python
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

    return "Entrada" if destinatario == cnpj_empresa else "Saída"

# Classificação Veículo x Consumo Inteligente
def classificar_produto(row):
    if row.get('Chassi') or row.get('Placa') or row.get('Renavam'):
        return "Veículo"
    produto = str(row.get('Produto') or "").lower()
    termos = ['veículo', 'veiculo', 'automóvel', 'automovel', 'caminhão', 'caminhao', 
              'motocicleta', 'moto', 'bmw', 'civic', 'chassi', 'placa']
    if any(t in produto for t in termos):
        return "Veículo"
    return "Consumo"

# Função para extrair informações adicionais do Produto
def extrair_informacoes_adicionais(df):
    for idx, row in df.iterrows():
        produto = str(row.get('Produto') or "")

        motor_match = re.search(r'Motor:\s*([A-Z0-9\-]+)', produto, re.IGNORECASE)
        if motor_match and pd.isna(df.at[idx, 'Motor']):
            df.at[idx, 'Motor'] = motor_match.group(1).strip()

        placa_match = re.search(r'Placa:\s*([A-Z0-9]{7})', produto, re.IGNORECASE)
        if placa_match and pd.isna(df.at[idx, 'Placa']):
            df.at[idx, 'Placa'] = placa_match.group(1).strip()

        modelo_match = re.search(r'-\s*([A-Za-zÀ-ú0-9\s]+(?:\s[A-Z]{3}\s)?)', produto)
        if modelo_match and pd.isna(df.at[idx, 'Modelo']):
            df.at[idx, 'Modelo'] = modelo_match.group(1).strip()

        lotacao_match = re.search(r'Lotacao:\s*(\d+)', produto, re.IGNORECASE)
        if lotacao_match:
            df.at[idx, 'Lotacao'] = lotacao_match.group(1).strip()
    return df

# Função principal de extração
def extrair_dados_xml(xml_path):
    try:
        tree = ET.parse(xml_path)
        root = tree.getroot()
        ns = {'nfe': 'http://www.portalfiscal.inf.br/nfe'}

        cabecalho = {
            'Emitente Nome': root.findtext('.//nfe:emit/nfe:xNome', namespaces=ns) or 'Não informado',
            'Emitente CNPJ': root.findtext('.//nfe:emit/nfe:CNPJ', namespaces=ns) or 'Não informado',
            'Destinatário Nome': root.findtext('.//nfe:dest/nfe:xNome', namespaces=ns) or 'Não informado',
            'Destinatário CNPJ': root.findtext('.//nfe:dest/nfe:CNPJ', namespaces=ns) or 'Não informado',
            'CFOP': root.findtext('.//nfe:det/nfe:prod/nfe:CFOP', namespaces=ns),
            'Data Emissão': root.findtext('.//nfe:ide/nfe:dhEmi', namespaces=ns),
            'Valor Total': root.findtext('.//nfe:total/nfe:ICMSTot/nfe:vNF', namespaces=ns)
        }

        registros = []
        campos_padrao = list(LAYOUT_COLUNAS.keys()) + ['Produto']

        for item in root.findall('.//nfe:det', ns):
            dados = {col: None for col in campos_padrao}
            dados.update(cabecalho)

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

# Processar XMLs
def processar_xmls(xml_paths, cnpj_empresa):
    todos_registros = []
    for p in xml_paths:
        registros = extrair_dados_xml(p)
        if registros:
            todos_registros.extend(registros)

    if not todos_registros:
        log.error("Nenhum dado extraído.")
        return pd.DataFrame()

    df = pd.DataFrame(todos_registros)

    df = extrair_informacoes_adicionais(df)

    df['Tipo Nota'] = df.apply(lambda row: classificar_tipo_nota(row['Emitente CNPJ'], row['Destinatário CNPJ'], cnpj_empresa), axis=1)
    df['Tipo Produto'] = df.apply(classificar_produto, axis=1)

    # Padronizar nomes de colunas
    df.rename(columns={
        'Destinatario Nome': 'Destinatário Nome',
        'Destinatario CNPJ': 'Destinatário CNPJ',
        'Emitente Nome': 'Emitente Nome',
        'Emitente CNPJ': 'Emitente CNPJ'
    }, inplace=True)

    return df
