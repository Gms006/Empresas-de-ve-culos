import pandas as pd
from lxml import etree
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

with open('empresas_config.json', encoding='utf-8') as f:
    CONFIG_EMPRESA = json.load(f)['bda']

with open('validador_veiculo.json', encoding='utf-8') as f:
    VALIDADORES = json.load(f)

CNPJS_EMPRESA = CONFIG_EMPRESA['cnpj_emitentes']
NOMES_EMPRESA = [nome.lower() for nome in CONFIG_EMPRESA['nomes_proprios']]

CFOPS_SAIDA = ["5101", "5102", "5103", "5949", "6101", "6102", "6108", "6949"]
CLIENTE_FINAL_REF = "cliente final"

CAMPOS_OBRIGATORIOS = ['CFOP', 'Data Emissão', 'Valor Total']

# ===== Validações =====
def validar_chassi(chassi):
    return bool(chassi) and re.fullmatch(VALIDADORES["chassi"], chassi)

def validar_placa(placa):
    return bool(placa) and (
        re.fullmatch(VALIDADORES["placa_mercosul"], placa) or
        re.fullmatch(VALIDADORES["placa_antiga"], placa)
    )

# ===== Extração Corrigida com lxml + XPath =====
def extrair_dados_xml(xml_path):
    try:
        log.info(f"Processando XML: {xml_path}")
        tree = etree.parse(xml_path)
        root = tree.getroot()

        dados = {}
        for campo, paths in MAPA_CAMPOS.items():
            valor = None
            for path in paths:
                resultado = root.xpath(path)
                if resultado:
                    primeiro = resultado[0]
                    if isinstance(primeiro, etree._Element) and primeiro.text:
                        valor = primeiro.text.strip()
                        break
                    elif isinstance(primeiro, str):
                        valor = primeiro.strip()
                        break
            dados[campo] = valor
            if not valor and campo in CAMPOS_OBRIGATORIOS:
                log.warning(f"Campo obrigatório '{campo}' não encontrado no XML.")

        texto_xml = etree.tostring(root, encoding='unicode')
        for campo, padrao in REGEX_EXTRACAO.items():
            if not dados.get(campo):
                match = re.search(padrao, texto_xml)
                if match:
                    dados[campo] = match.group(1)

        if not validar_chassi(dados.get("Chassi")):
            log.warning(f"Chassi inválido.")
            dados["Chassi"] = None
        if not validar_placa(dados.get("Placa")):
            log.warning(f"Placa inválida.")
            dados["Placa"] = None

        if any(not dados.get(campo) for campo in CAMPOS_OBRIGATORIOS):
            log.error(f"XML ignorado por falta de campos essenciais.")
            return None

        return dados
    except Exception as e:
        log.error(f"Erro ao processar {xml_path}: {e}")
        return None

# ===== Classificação =====
def classificar_tipo_nota(row):
    tipo_nf = str(row.get('Tipo NF') or "").strip()
    if tipo_nf == "1":
        log.info(f"Classificado como Saída via Tipo NF")
        return "Saída"
    if tipo_nf == "0":
        log.info(f"Classificado como Entrada via Tipo NF")
        return "Entrada"

    emitente_cnpj = (row.get('Emitente CNPJ') or "").zfill(14)
    destinatario_cnpj = (row.get('Destinatário CNPJ') or "").zfill(14)
    emitente_nome = (row.get('Emitente Nome') or "").lower()
    destinatario_nome = (row.get('Destinatário Nome') or "").lower()
    cfop = str(row.get('CFOP') or "").strip()

    if emitente_cnpj in CNPJS_EMPRESA:
        return "Saída"
    if destinatario_cnpj in CNPJS_EMPRESA:
        return "Entrada"
    if any(nome in emitente_nome for nome in NOMES_EMPRESA):
        return "Saída"
    if any(nome in destinatario_nome for nome in NOMES_EMPRESA):
        return "Entrada"
    if cfop in CFOPS_SAIDA:
        return "Saída"
    if CLIENTE_FINAL_REF in destinatario_nome:
        return "Saída"

    log.warning(f"Classificação padrão aplicada: Entrada")
    return "Entrada"

# ===== Processamento Principal =====
def processar_arquivos_xml(xml_paths):
    registros = [extrair_dados_xml(path) for path in xml_paths if path.endswith(".xml")]
    df = pd.DataFrame(filter(None, registros))

    colunas_finais = list(set(MAPA_CAMPOS.keys()).union(REGEX_EXTRACAO.keys()))
    colunas_finais += ['Tipo Nota', 'Data Entrada', 'Data Saída']

    if not df.empty:
        df['Tipo Nota'] = df.apply(classificar_tipo_nota, axis=1)
        df['Data Entrada'] = pd.to_datetime(df['Data Emissão'], errors='coerce')
        df['Data Saída'] = pd.to_datetime(
            df.apply(lambda row: row['Data Emissão'] if row['Tipo Nota'] == "Saída" else pd.NaT, axis=1),
            errors='coerce'
        )
    else:
        log.warning("Nenhum registro válido encontrado.")
        df = pd.DataFrame(columns=colunas_finais)

    for col in colunas_finais:
        if col not in df.columns:
            df[col] = None

    log.info(f"\n=== RESUMO FINAL ===")
    log.info(f"XMLs processados: {len(xml_paths)}")
    log.info(f"Notas válidas: {len(df)}")
    log.info(f"Entradas detectadas: {df[df['Tipo Nota'] == 'Entrada'].shape[0]}")
    log.info(f"Saídas detectadas: {df[df['Tipo Nota'] == 'Saída'].shape[0]}")

    return df[df['Tipo Nota'] == "Entrada"].copy(), df[df['Tipo Nota'] == "Saída"].copy()
