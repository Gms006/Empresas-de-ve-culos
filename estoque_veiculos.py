import pandas as pd
import xml.etree.ElementTree as ET
import json
import re

# ====== Carregar Configurações ======
with open('mapa_campos_extracao.json', encoding='utf-8') as f:
    MAPA_CAMPOS = json.load(f)

with open('regex_extracao.json', encoding='utf-8') as f:
    REGEX_EXTRACAO = json.load(f)

with open('empresas_config.json', encoding='utf-8') as f:
    CONFIG_EMPRESA = json.load(f)['bda']

CNPJS_EMPRESA = CONFIG_EMPRESA['cnpj_emitentes']
NOMES_EMPRESA = [nome.lower() for nome in CONFIG_EMPRESA['nomes_proprios']]

CFOPS_SAIDA = ["5101", "5102", "5103", "5949", "6101", "6102", "6108", "6949"]
CLIENTE_FINAL_REF = "cliente final"

# ====== Campos Obrigatórios ======
CAMPOS_OBRIGATORIOS = ['CFOP', 'Data Emissão', 'Valor Total']
CAMPOS_COMPLEMENTARES = ['Chassi', 'Placa', 'Emitente CNPJ', 'Destinatário CNPJ', 'Emitente Nome', 'Destinatário Nome']

def extrair_dados_xml(xml_path):
    try:
        tree = ET.parse(xml_path)
        root = tree.getroot()
        ns = {'nfe': 'http://www.portalfiscal.inf.br/nfe'}

        dados = {}
        # Extração via XPath
        for campo, paths in MAPA_CAMPOS.items():
            valor = None
            for path in paths:
                elemento = root.find(path, ns) or root.find(path)
                if elemento is not None and elemento.text:
                    valor = elemento.text.strip()
                    break
            dados[campo] = valor

        # Complementar com Regex
        texto_xml = ET.tostring(root, encoding='unicode')
        for campo, padrao in REGEX_EXTRACAO.items():
            if not dados.get(campo):
                match = re.search(padrao, texto_xml)
                if match:
                    dados[campo] = match.group(1)

        # Validar campos essenciais
        if any(not dados.get(campo) for campo in CAMPOS_OBRIGATORIOS):
            return None

        return dados
    except Exception:
        return None

def classificar_tipo_nota(row):
    emitente_cnpj = (row.get('Emitente CNPJ') or "").zfill(14)
    destinatario_cnpj = (row.get('Destinatário CNPJ') or "").zfill(14)
    emitente_nome = (row.get('Emitente Nome') or "").lower()
    destinatario_nome = (row.get('Destinatário Nome') or "").lower()
    cfop = str(row.get('CFOP') or "").strip()

    # 1️⃣ CNPJ da Empresa
    if emitente_cnpj in CNPJS_EMPRESA:
        return "Saída"
    if destinatario_cnpj in CNPJS_EMPRESA:
        return "Entrada"

    # 2️⃣ Nome da Empresa
    if any(nome in emitente_nome for nome in NOMES_EMPRESA):
        return "Saída"
    if any(nome in destinatario_nome for nome in NOMES_EMPRESA):
        return "Entrada"

    # 3️⃣ Fallback - CFOP ou Cliente Final
    if cfop in CFOPS_SAIDA:
        return "Saída"
    if CLIENTE_FINAL_REF in destinatario_nome:
        return "Saída"

    # 4️⃣ Caso não identifique
    return "Entrada"  # Assume Entrada como padrão seguro

def processar_arquivos_xml(xml_paths):
    registros = [extrair_dados_xml(path) for path in xml_paths if path.endswith(".xml")]
    df = pd.DataFrame(filter(None, registros))

    # Garantir todas as colunas essenciais e complementares
    for col in set(CAMPOS_OBRIGATORIOS + CAMPOS_COMPLEMENTARES):
        if col not in df.columns:
            df[col] = None

    if not df.empty:
        df['Tipo Nota'] = df.apply(classificar_tipo_nota, axis=1)
        df['Data Entrada'] = pd.to_datetime(df['Data Emissão'], errors='coerce')
        df['Data Saída'] = df.apply(lambda row: row['Data Emissão'] if row['Tipo Nota'] == "Saída" else pd.NaT, axis=1)
        df['Data Saída'] = pd.to_datetime(df['Data Saída'], errors='coerce')
    else:
        df = pd.DataFrame(columns=list(CAMPOS_OBRIGATORIOS + CAMPOS_COMPLEMENTARES + ['Tipo Nota', 'Data Entrada', 'Data Saída']))

    # Logs
    print(f"📊 Total XMLs processados: {len(xml_paths)}")
    print(f"✅ Notas válidas: {len(df)}")
    print(f"📥 Entradas: {df[df['Tipo Nota'] == 'Entrada'].shape[0]}")
    print(f"📤 Saídas: {df[df['Tipo Nota'] == 'Saída'].shape[0]}")

    return df[df['Tipo Nota'] == "Entrada"].copy(), df[df['Tipo Nota'] == "Saída"].copy()
