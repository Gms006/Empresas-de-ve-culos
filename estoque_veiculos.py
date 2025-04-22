
import pandas as pd
from lxml import etree
import json
import re
from collections import Counter

with open('mapa_campos_extracao.json', encoding='utf-8') as f:
    MAPA_CAMPOS = json.load(f)
with open('regex_extracao.json', encoding='utf-8') as f:
    REGEX_EXTRACAO = json.load(f)

# Definir quais campos são padrão e quais são complementares de veículo
CAMPOS_PADRAO = ['CFOP', 'Data Emissão', 'Destinatário Nome', 'Destinatário CNPJ', 'Emitente Nome', 'Emitente CNPJ', 'Valor Total', 'Produto']
CAMPOS_VEICULO = ['Chassi', 'Placa', 'Renavam']

def extrair_dados_xml(xml_path, contador_falhas, erros_criticos):
    try:
        with open(xml_path, 'rb') as f:
            tree = etree.parse(f)

        dados = {}

        # 1️⃣ Extração dos campos padrão (obrigatórios em qualquer NF-e)
        for campo in CAMPOS_PADRAO:
            paths = MAPA_CAMPOS.get(campo, [])
            if isinstance(paths, str):
                paths = [paths]
            valor = None
            for path in paths:
                resultado = tree.xpath(f'//*[local-name() = "{path.split("/")[-1]}"]')
                if resultado and resultado[0].text:
                    valor = resultado[0].text
                    break
            dados[campo] = valor
            if not valor:
                contador_falhas[campo] += 1

        # 2️⃣ Verificar se é uma nota de veículo (pelo CFOP ou Produto)
        cfop_detectado = str(dados.get('CFOP', '')).strip()
        produto_desc = str(dados.get('Produto', '')).lower()

        if cfop_detectado.startswith('5') or 'veículo' in produto_desc:
            dados['Tipo Nota Fiscal'] = 'Veículo'
            for campo in CAMPOS_VEICULO:
                paths = MAPA_CAMPOS.get(campo, [])
                if isinstance(paths, str):
                    paths = [paths]
                valor = None
                for path in paths:
                    resultado = tree.xpath(f'//*[local-name() = "{path.split("/")[-1]}"]')
                    if resultado and resultado[0].text:
                        valor = resultado[0].text
                        break
                dados[campo] = valor
                if not valor:
                    contador_falhas[campo] += 1
        else:
            dados['Tipo Nota Fiscal'] = 'Padrão'

        # Aplicar regex complementares
        texto_xml = etree.tostring(tree, encoding='unicode')
        for campo, padrao in REGEX_EXTRACAO.items():
            match = re.search(padrao, texto_xml)
            if match:
                dados[campo] = match.group(1)
            else:
                contador_falhas[campo] += 1

        return dados
    except Exception as e:
        erros_criticos.append(f"{xml_path} -> {str(e)}")
        return None

def processar_arquivos_xml(xml_paths):
    open("log_extracao.txt", "w").close()

    registros = []
    contador_falhas = Counter()
    erros_criticos = []

    for path in xml_paths:
        if path.endswith(".xml"):
            registro = extrair_dados_xml(path, contador_falhas, erros_criticos)
            if registro:
                registros.append(registro)

    df = pd.DataFrame(registros)

    # Garantir colunas principais
    for col in CAMPOS_PADRAO + CAMPOS_VEICULO:
        if col not in df.columns:
            df[col] = None

    cfops_saida = ["5101", "5102", "5103", "5949", "6101", "6102", "6108", "6949"]
    cliente_final_ref = "cliente final"

    def classificar_saida(row):
        cfop = str(row['CFOP']).strip() if row['CFOP'] else ""
        destinatario = str(row['Destinatário Nome']).lower() if row['Destinatário Nome'] else ""
        if cfop in cfops_saida or cliente_final_ref in destinatario:
            return "Saída"
        return "Entrada"

    df['Tipo Operação'] = df.apply(classificar_saida, axis=1)

    entradas = df[df['Tipo Operação'] == "Entrada"].shape[0]
    saidas = df[df['Tipo Operação'] == "Saída"].shape[0]

    with open("log_extracao.txt", "a", encoding="utf-8") as log:
        log.write(f"📊 RESUMO DA EXTRAÇÃO\n")
        log.write(f"- XMLs processados: {len(xml_paths)}\n")
        log.write(f"- Sucesso: {len(registros)}\n")
        log.write(f"- Erros críticos: {len(erros_criticos)}\n")
        log.write(f"- Notas de Entrada: {entradas}\n")
        log.write(f"- Notas de Saída: {saidas}\n\n")

    df['Data Entrada'] = pd.to_datetime(df['Data Emissão'], errors='coerce')
    df['Data Saída'] = df.apply(lambda row: row['Data Emissão'] if row['Tipo Operação'] == "Saída" else pd.NaT, axis=1)
    df['Data Saída'] = pd.to_datetime(df['Data Saída'], errors='coerce')

    df_entrada = df[df['Tipo Operação'] == "Entrada"].copy()
    df_saida = df[df['Tipo Operação'] == "Saída"].copy()

    return df_entrada, df_saida
