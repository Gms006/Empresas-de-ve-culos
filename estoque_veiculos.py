
import pandas as pd
import xml.etree.ElementTree as ET
import json
import re

# Carregar JSONs
with open('mapa_campos_extracao.json', encoding='utf-8') as f:
    MAPA_CAMPOS = json.load(f)
with open('regex_extracao.json', encoding='utf-8') as f:
    REGEX_EXTRACAO = json.load(f)

# Definir campos essenciais e complementares
CAMPOS_ESSENCIAIS = ['CFOP', 'Data Emissão', 'Destinatário Nome', 'Valor Total']
CAMPOS_COMPLEMENTARES = ['Chassi', 'Placa', 'Renavam']

def extrair_dados_xml(xml_path, log_erros):
    try:
        tree = ET.parse(xml_path)
        root = tree.getroot()
        ns = {'nfe': 'http://www.portalfiscal.inf.br/nfe'}

        dados = {}

        # 1️⃣ Extrair Campos Essenciais
        for campo in CAMPOS_ESSENCIAIS:
            paths = MAPA_CAMPOS.get(campo, [])
            if isinstance(paths, str):
                paths = [paths]
            valor = None
            for path in paths:
                elemento = root.find(path, ns) or root.find(path)
                if elemento is not None and elemento.text:
                    valor = elemento.text
                    break
            dados[campo] = valor

        # Validar se os dados essenciais foram encontrados
        if not dados['CFOP'] or not dados['Data Emissão'] or not dados['Valor Total']:
            log_erros['Notas inválidas - dados fiscais ausentes'] += 1
            return None

        # 2️⃣ Detectar se é Nota de Veículo
        produto_desc = str(dados.get('Produto', '')).lower()
        cfop = str(dados.get('CFOP', ''))
        is_veiculo = 'veiculo' in produto_desc or cfop.startswith('5')

        if is_veiculo:
            # 3️⃣ Buscar Campos Complementares
            for campo in CAMPOS_COMPLEMENTARES:
                paths = MAPA_CAMPOS.get(campo, [])
                if isinstance(paths, str):
                    paths = [paths]
                valor = None
                for path in paths:
                    elemento = root.find(path, ns) or root.find(path)
                    if elemento is not None and elemento.text:
                        valor = elemento.text
                        break
                if not valor:
                    # Aplicar regex como fallback
                    texto_xml = ET.tostring(root, encoding='unicode')
                    padrao = REGEX_EXTRACAO.get(campo)
                    if padrao:
                        match = re.search(padrao, texto_xml)
                        if match:
                            valor = match.group(1)
                if not valor:
                    log_erros[f'{campo} ausente'] += 1
                dados[campo] = valor
        else:
            log_erros['Notas comuns (não veículo)'] += 1

        return dados
    except Exception:
        log_erros['Erros críticos de parsing'] += 1
        return None

def processar_arquivos_xml(xml_paths):
    from collections import Counter
    log_erros = Counter()

    registros = [extrair_dados_xml(path, log_erros) for path in xml_paths if path.endswith(".xml")]
    registros_validos = list(filter(None, registros))

    df = pd.DataFrame(registros_validos)

    # Garantir todas as colunas presentes
    for col in CAMPOS_ESSENCIAIS + CAMPOS_COMPLEMENTARES:
        if col not in df.columns:
            df[col] = None

    # Classificação
    cfops_saida = ["5101", "5102", "5103", "5949", "6101", "6102", "6108", "6949"]
    cliente_final_ref = "cliente final"

    if not df.empty:
        df['Tipo Nota'] = df.apply(lambda row: "Saída" if str(row['CFOP']).strip() in cfops_saida or cliente_final_ref in str(row['Destinatário Nome']).lower() else "Entrada", axis=1)
        df['Data Entrada'] = pd.to_datetime(df['Data Emissão'], errors='coerce')
        df['Data Saída'] = df.apply(lambda row: row['Data Emissão'] if row['Tipo Nota'] == "Saída" else pd.NaT, axis=1)
        df['Data Saída'] = pd.to_datetime(df['Data Saída'], errors='coerce')
    else:
        df['Tipo Nota'] = None

    # Logs Resumidos
    print(f"📊 RESUMO FINAL")
    print(f"- XMLs processados: {len(xml_paths)}")
    print(f"- Notas válidas: {len(registros_validos)}")
    for erro, qtd in log_erros.items():
        print(f"- {erro}: {qtd}")

    return df[df['Tipo Nota'] == "Entrada"].copy(), df[df['Tipo Nota'] == "Saída"].copy()
