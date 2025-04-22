import pandas as pd
import xml.etree.ElementTree as ET
import json
import re

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

# ===== Funções de Validação =====
def validar_chassi(chassi):
    return bool(chassi) and re.fullmatch(VALIDADORES["chassi"], chassi)

def validar_placa(placa):
    return bool(placa) and (
        re.fullmatch(VALIDADORES["placa_mercosul"], placa) or
        re.fullmatch(VALIDADORES["placa_antiga"], placa)
    )

# ===== Função de Extração com LOG =====
def extrair_dados_xml(xml_path):
    try:
        print(f"🔍 Processando XML: {xml_path}")
        tree = ET.parse(xml_path)
        root = tree.getroot()
        ns = {'nfe': 'http://www.portalfiscal.inf.br/nfe'}

        dados = {}
        for campo, paths in MAPA_CAMPOS.items():
            valor = None
            for path in paths:
                elemento = root.find(path, ns) or root.find(path)
                if elemento is not None and elemento.text:
                    valor = elemento.text.strip()
                    break
            dados[campo] = valor
            if not valor and campo in CAMPOS_OBRIGATORIOS:
                print(f"⚠️ Campo obrigatório '{campo}' não encontrado no XML: {xml_path}")

        texto_xml = ET.tostring(root, encoding='unicode')
        for campo, padrao in REGEX_EXTRACAO.items():
            if not dados.get(campo):
                match = re.search(padrao, texto_xml)
                if match:
                    dados[campo] = match.group(1)

        if not validar_chassi(dados.get("Chassi")):
            print(f"⚠️ Chassi inválido no XML: {xml_path}")
            dados["Chassi"] = None
        if not validar_placa(dados.get("Placa")):
            print(f"⚠️ Placa inválida no XML: {xml_path}")
            dados["Placa"] = None

        if any(not dados.get(campo) for campo in CAMPOS_OBRIGATORIOS):
            print(f"⛔ XML ignorado por falta de campos essenciais: {xml_path}")
            return None

        return dados
    except Exception as e:
        print(f"❌ Erro ao processar {xml_path}: {e}")
        return None

# ===== Classificação com LOG =====
def classificar_tipo_nota(row):
    tipo_nf = str(row.get('Tipo NF') or "").strip()
    if tipo_nf == "1":
        print(f"🏷️ Classificado como Saída via Tipo NF")
        return "Saída"
    if tipo_nf == "0":
        print(f"🏷️ Classificado como Entrada via Tipo NF")
        return "Entrada"

    emitente_cnpj = (row.get('Emitente CNPJ') or "").zfill(14)
    destinatario_cnpj = (row.get('Destinatário CNPJ') or "").zfill(14)
    emitente_nome = (row.get('Emitente Nome') or "").lower()
    destinatario_nome = (row.get('Destinatário Nome') or "").lower()
    cfop = str(row.get('CFOP') or "").strip()

    if emitente_cnpj in CNPJS_EMPRESA:
        print(f"🏷️ Classificado como Saída via Emitente CNPJ")
        return "Saída"
    if destinatario_cnpj in CNPJS_EMPRESA:
        print(f"🏷️ Classificado como Entrada via Destinatário CNPJ")
        return "Entrada"
    if any(nome in emitente_nome for nome in NOMES_EMPRESA):
        print(f"🏷️ Classificado como Saída via Nome Emitente")
        return "Saída"
    if any(nome in destinatario_nome for nome in NOMES_EMPRESA):
        print(f"🏷️ Classificado como Entrada via Nome Destinatário")
        return "Entrada"
    if cfop in CFOPS_SAIDA:
        print(f"🏷️ Classificado como Saída via CFOP")
        return "Saída"
    if CLIENTE_FINAL_REF in destinatario_nome:
        print(f"🏷️ Classificado como Saída via Cliente Final")
        return "Saída"

    print(f"⚠️ Classificação padrão aplicada: Entrada")
    return "Entrada"

# ===== Processamento Principal com LOG FINAL =====
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
        print("⚠️ Nenhum registro válido encontrado.")
        df = pd.DataFrame(columns=colunas_finais)

    for col in colunas_finais:
        if col not in df.columns:
            df[col] = None

    print(f"\n📊 === RESUMO FINAL ===")
    print(f"XMLs processados: {len(xml_paths)}")
    print(f"Notas válidas: {len(df)}")
    print(f"Entradas detectadas: {df[df['Tipo Nota'] == 'Entrada'].shape[0]}")
    print(f"Saídas detectadas: {df[df['Tipo Nota'] == 'Saída'].shape[0]}")

    return df[df['Tipo Nota'] == "Entrada"].copy(), df[df['Tipo Nota'] == "Saída"].copy()
