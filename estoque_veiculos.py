import pandas as pd
import xml.etree.ElementTree as ET
import json
import re
import logging

# ===== Configuração de Logging =====
logging.basicConfig(level=logging.INFO, format='%(levelname)s: %(message)s')
log = logging.getLogger(__name__)

# ===== Carregar Configurações =====
with open('mapa_campos_extracao.json', encoding='utf-8') as f:
    MAPA_CAMPOS = json.load(f)

with open('regex_extracao.json', encoding='utf-8') as f:
    REGEX_EXTRACAO = json.load(f)

with open('validador_veiculo.json', encoding='utf-8') as f:
    VALIDADORES = json.load(f)

# ===== Parâmetros de Classificação =====
CFOPS_SAIDA = ["5101", "5102", "5103", "5949", "6101", "6102", "6108", "6949"]
CLIENTE_FINAL_REF = "cliente final"

# ===== Funções de Validação =====
def validar_chassi(chassi):
    return bool(chassi) and re.fullmatch(VALIDADORES["chassi"], chassi)

def validar_placa(placa):
    return bool(placa) and (
        re.fullmatch(VALIDADORES["placa_mercosul"], placa) or
        re.fullmatch(VALIDADORES["placa_antiga"], placa)
    )

# ===== Função de Extração por XML =====
def extrair_dados_xml(xml_path):
    try:
        tree = ET.parse(xml_path)
        root = tree.getroot()

        dados = {}

        # Extração via MAPA_CAMPOS (XPath simples)
        for campo, path in MAPA_CAMPOS.items():
            elemento = root.find(path)
            dados[campo] = elemento.text.strip() if elemento is not None and elemento.text else None

        # Extração via REGEX
        texto_xml = ET.tostring(root, encoding='unicode')
        for campo, padrao in REGEX_EXTRACAO.items():
            match = re.search(padrao, texto_xml, re.IGNORECASE)
            dados[campo] = match.group(1).strip() if match else None

        # Validação de Chassi e Placa
        if not validar_chassi(dados.get("Chassi")):
            log.warning(f"{xml_path} - Chassi inválido ou ausente.")
            dados["Chassi"] = None
        if not validar_placa(dados.get("Placa")):
            log.warning(f"{xml_path} - Placa inválida ou ausente.")
            dados["Placa"] = None

        dados["Fonte XML"] = xml_path  # Para rastreabilidade
        return dados

    except Exception as e:
        log.error(f"Erro crítico ao processar {xml_path}: {e}")
        return None

# ===== Classificação Segura =====
def classificar_tipo(row):
    cfop = str(row.get('CFOP') or "").strip()
    destinatario = str(row.get('Destinatário Nome') or "").lower()

    if cfop in CFOPS_SAIDA:
        return "Saída"
    if CLIENTE_FINAL_REF in destinatario:
        return "Saída"
    if cfop:
        return "Entrada"
    return "Não Classificado"

# ===== Processamento Principal =====
def processar_arquivos_xml(xml_paths):
    registros = []
    for path in xml_paths:
        if path.endswith(".xml"):
            log.info(f"Processando: {path}")
            dados = extrair_dados_xml(path)
            if dados:
                registros.append(dados)

    df = pd.DataFrame(registros)

    if df.empty:
        log.warning("Nenhum registro válido extraído.")
        return pd.DataFrame(), pd.DataFrame()

    # Garantir colunas mínimas
    campos_esperados = list(MAPA_CAMPOS.keys()) + list(REGEX_EXTRACAO.keys()) + ['Tipo Nota', 'Data Entrada', 'Data Saída', 'Fonte XML']
    for col in campos_esperados:
        if col not in df.columns:
            df[col] = None

    # Aplicar Classificação
    df['Tipo Nota'] = df.apply(classificar_tipo, axis=1)

    # Tratamento de Datas
    df['Data Entrada'] = pd.to_datetime(df['Data Emissão'], errors='coerce')
    df['Data Saída'] = df.apply(lambda row: row['Data Emissão'] if row['Tipo Nota'] == "Saída" else pd.NaT, axis=1)
    df['Data Saída'] = pd.to_datetime(df['Data Saída'], errors='coerce')

    # Logs Finais
    log.info(f"\n=== RESUMO FINAL ===")
    log.info(f"XMLs processados: {len(xml_paths)}")
    log.info(f"Notas extraídas: {len(df)}")
    log.info(f"Entradas: {df[df['Tipo Nota'] == 'Entrada'].shape[0]}")
    log.info(f"Saídas: {df[df['Tipo Nota'] == 'Saída'].shape[0]}")
    log.info(f"Não Classificadas: {df[df['Tipo Nota'] == 'Não Classificado'].shape[0]}")

    return df[df['Tipo Nota'] == "Entrada"].copy(), df[df['Tipo Nota'] == "Saída"].copy()

