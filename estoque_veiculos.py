
import os
import re
import json
import xml.etree.ElementTree as ET
from datetime import datetime
import pandas as pd

# Carregamento de configurações via JSON externo
with open("mapa_campos_extracao.json", "r", encoding="utf-8") as f:
    mapa = json.load(f)
with open("formato_colunas.json", "r", encoding="utf-8") as f:
    formato = json.load(f)
with open("ordem_colunas.json", "r", encoding="utf-8") as f:
    ordem = json.load(f)["ordem_preferida"]

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

                # Determinar tipo (Entrada/Saída)
                cnpj_emitente = obter_valor(ns, "CNPJ", emit)
                nome_destinatario = obter_valor(ns, "xNome", dest).upper()
                cfop = obter_valor(ns, "CFOP", prod)
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
