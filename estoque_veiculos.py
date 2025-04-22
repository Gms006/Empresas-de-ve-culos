import pandas as pd
from lxml import etree
from collections import Counter

# ===== JSON EMBUTIDO =====
MAPA_CAMPOS = {
    "essenciais": {
        "CFOP": ["//*[local-name()='CFOP']"],
        "Data Emissão": ["//*[local-name()='dhEmi']"],
        "Destinatário Nome": ["//*[local-name()='dest']/*[local-name()='xNome']"],
        "Valor Total": ["//*[local-name()='vNF']"]
    },
    "complementares": {
        "Chassi": ["//*[local-name()='chassi']"],
        "Placa": ["//*[local-name()='placa']"],
        "Renavam": ["//*[local-name()='RENAVAM']"]
    }
}

def extrair_valor_xpath(tree, paths):
    for path in paths:
        resultado = tree.xpath(path)
        if resultado and isinstance(resultado[0], etree._Element):
            return resultado[0].text
        elif resultado:
            return resultado[0]
    return None

def extrair_dados_xml(xml_path, log_erros):
    try:
        with open(xml_path, 'rb') as f:
            tree = etree.parse(f)

        dados = {}
        for grupo in MAPA_CAMPOS.values():
            for campo, paths in grupo.items():
                valor = extrair_valor_xpath(tree, paths)
                dados[campo] = valor
                if not valor:
                    log_erros[f'{campo} ausente'] += 1

        if not dados['CFOP'] or not dados['Data Emissão'] or not dados['Valor Total']:
            log_erros['Notas inválidas - dados fiscais incompletos'] += 1
            return None

        return dados
    except Exception:
        log_erros['Erro crítico de parsing'] += 1
        return None

def processar_arquivos_xml(xml_paths):
    log_erros = Counter()
    registros = [extrair_dados_xml(path, log_erros) for path in xml_paths if path.endswith(".xml")]
    registros_validos = list(filter(None, registros))

    df = pd.DataFrame(registros_validos)

    todas_colunas = list(MAPA_CAMPOS['essenciais'].keys()) + list(MAPA_CAMPOS['complementares'].keys())
    for col in todas_colunas:
        if col not in df.columns:
            df[col] = None

    cfops_saida = ["5101", "5102", "5103", "5949", "6101", "6102", "6108", "6949"]
    cliente_final_ref = "cliente final"

    if not df.empty:
        df['Tipo Nota'] = df.apply(
            lambda row: "Saída" if str(row['CFOP']).strip() in cfops_saida or cliente_final_ref in str(row['Destinatário Nome']).lower() else "Entrada",
            axis=1
        )
        df['Data Entrada'] = pd.to_datetime(df['Data Emissão'], errors='coerce')
        df['Data Saída'] = df.apply(lambda row: row['Data Emissão'] if row['Tipo Nota'] == "Saída" else pd.NaT, axis=1)
        df['Data Saída'] = pd.to_datetime(df['Data Saída'], errors='coerce')
        print(f"✅ Classificação aplicada. Total: {len(df)} notas.")
    else:
        df = pd.DataFrame(columns=todas_colunas + ['Tipo Nota', 'Data Entrada', 'Data Saída'])
        print("⚠️ DataFrame vazio. Nenhuma nota classificada.")

    print(f"📊 RESUMO FINAL")
    print(f"- XMLs processados: {len(xml_paths)}")
    print(f"- Notas válidas: {len(registros_validos)}")
    print(f"- Notas de Entrada: {df[df['Tipo Nota'] == 'Entrada'].shape[0] if not df.empty else 0}")
    print(f"- Notas de Saída: {df[df['Tipo Nota'] == 'Saída'].shape[0] if not df.empty else 0}")
    for erro, qtd in log_erros.items():
        print(f"- {erro}: {qtd}")

    return df[df['Tipo Nota'] == "Entrada"].copy(), df[df['Tipo Nota'] == "Saída"].copy()
