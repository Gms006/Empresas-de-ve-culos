
import os
import re
import json
import xml.etree.ElementTree as ET
import pandas as pd

# Carregamento dos JSONs
with open("mapa_campos_extracao.json", "r", encoding="utf-8") as f:
    mapa = json.load(f)
with open("formato_colunas.json", "r", encoding="utf-8") as f:
    formato = json.load(f)
with open("ordem_colunas.json", "r", encoding="utf-8") as f:
    ordem = json.load(f)["ordem_preferida"]
with open("regex_extracao.json", "r", encoding="utf-8") as f:
    regex = json.load(f)

def obter_valor(ns, tag, contexto):
    try:
        valor = contexto.find(f"ns:{tag}", ns)
        return valor.text if valor is not None else ""
    except:
        return ""

def aplicar_tipo(valor, campo, formato):
    try:
        if not valor:
            return 0.0 if campo in formato.get("moeda", []) or campo in formato.get("percentual", []) else 0
        if campo in formato.get("moeda", []) or campo in formato.get("percentual", []):
            return float(str(valor).replace(",", "."))
        elif campo in formato.get("inteiro", []):
            return int(float(valor))
        else:
            return valor
    except:
        return valor

def aplicar_regex_extracao(texto):
    resultado = {}
    for campo, padroes in regex.items():
        for padrao in padroes if isinstance(padroes, list) else [padroes]:
            match = re.search(padrao, texto, flags=re.IGNORECASE)
            if match:
                resultado[campo] = match.group(1).strip()
                break
    return resultado

def reordenar_colunas(df, ordem):
    if df.empty:
        return df
    colunas = [c for c in ordem if c in df.columns] + [c for c in df.columns if c not in ordem]
    return df[colunas]

def processar_arquivos_xml(lista_de_caminhos):
    entradas, saidas = [], []
    erros = []

    for caminho in lista_de_caminhos:
        try:
            tree = ET.parse(caminho)
            root = tree.getroot()
            ns = {'ns': 'http://www.portalfiscal.inf.br/nfe'}
            infNFe = root.find(".//ns:infNFe", ns)

            if infNFe is None:
                raise ValueError("XML sem infNFe")

            emit = infNFe.find(".//ns:emit", ns)
            dest = infNFe.find(".//ns:dest", ns)
            ide = infNFe.find(".//ns:ide", ns)
            produtos = infNFe.findall(".//ns:det", ns)

            if None in [emit, dest, ide] or not produtos:
                raise ValueError("XML incompleto ou sem produtos")

            for det in produtos:
                linha = {}
                prod = det.find("ns:prod", ns)
                imposto = det.find("ns:imposto", ns)
                infAdProd = det.find("ns:infAdProd", ns)

                # Extração padrão pelo mapa
                for secao, campos in mapa.items():
                    if secao == "ide":
                        contexto = ide
                    elif secao == "emit":
                        contexto = emit
                    elif secao == "dest":
                        contexto = dest
                    elif secao == "prod":
                        contexto = prod
                    else:
                        contexto = imposto.find(f"ns:{secao}", ns) if imposto is not None else None

                    if contexto is not None:
                        for xml_tag, nome_coluna in campos.items():
                            valor = obter_valor(ns, xml_tag, contexto)
                            linha[nome_coluna] = aplicar_tipo(valor, nome_coluna, formato)

                # Extração adicional com regex sobre xProd e infAdProd
                xProd_texto = obter_valor(ns, "xProd", prod)
                adProd_texto = infAdProd.text if infAdProd is not None else ""
                texto_completo = f"{xProd_texto} {adProd_texto}".strip()

                campos_extras = aplicar_regex_extracao(texto_completo)

                # Fallback de chassi oculto (ex: dentro de Produto)
                if "chassi" not in campos_extras or not campos_extras.get("chassi"):
                    match_chassi_livre = re.search(r"(?<![A-Z0-9])[A-HJ-NPR-Z0-9]{17}(?![A-Z0-9])", texto_completo)
                    if match_chassi_livre:
                        campos_extras["chassi"] = match_chassi_livre.group(0)

                
    # Fallback de chassi oculto (ex: dentro de Produto)
    if "chassi" not in campos_extras or not campos_extras.get("chassi"):
        match_chassi_livre = re.search(r"(?<![A-Z0-9])[A-HJ-NPR-Z0-9]{17}(?![A-Z0-9])", texto_completo)
        if match_chassi_livre:
            campos_extras["chassi"] = match_chassi_livre.group(0)

    for campo, valor in campos_extras.items():

                    nome_coluna = {
                        "chassi": "Chassi",
                        "placa": "Placa",
                        "renavam": "Renavam",
                        "ano_modelo": "Ano Modelo",
                        "ano_fabricacao": "Ano Fabricação",
                        "cor": "Cor",
                        "km": "KM"
                    }.get(campo, campo)
                    linha[nome_coluna] = aplicar_tipo(valor, nome_coluna, formato)

                # Determinação de entrada/saída
                cfop = obter_valor(ns, "CFOP", prod)
                nome_destinatario = obter_valor(ns, "xNome", dest).upper()
                tipo = "Entrada" if cfop.startswith("1") or cfop.startswith("2") else (
                    "Entrada" if "BDA COMERCIO" in nome_destinatario else "Saída"
                )

                linha["Tipo"] = tipo
                if tipo == "Entrada":
                    entradas.append(linha)
                else:
                    saidas.append(linha)

        except Exception as e:
            erros.append((os.path.basename(caminho), str(e)))
            continue

    df_entrada = pd.DataFrame(entradas)
    df_saida = pd.DataFrame(saidas)

    df_entrada = reordenar_colunas(df_entrada, ordem)
    df_saida = reordenar_colunas(df_saida, ordem)

    return df_entrada, df_saida
