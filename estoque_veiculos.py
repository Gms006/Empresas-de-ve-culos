import os
import re
import json
import xml.etree.ElementTree as ET
import pandas as pd
from datetime import datetime

def obter_valor(ns, tag, contexto):
    try:
        return contexto.find(f"ns:{tag}", ns).text
    except:
        return ""

def aplicar_tipo(valor, campo, formato):
    try:
        if campo in formato.get("moeda", []) or campo in formato.get("percentual", []):
            return float(valor.replace(",", "."))
        elif campo in formato.get("inteiro", []):
            return int(float(valor))
        else:
            return str(valor).strip()
    except:
        return valor

def processar_arquivos_xml(lista_de_caminhos):
    with open("mapa_campos_extracao.json", "r", encoding="utf-8") as f:
        mapa = json.load(f)
    with open("formato_colunas.json", "r", encoding="utf-8") as f:
        formato = json.load(f)

    entradas, saidas = [], []
    for caminho in lista_de_caminhos:
        try:
            tree = ET.parse(caminho)
            root = tree.getroot()
            ns = {"ns": "http://www.portalfiscal.inf.br/nfe"}
            infNFe = root.find(".//ns:infNFe", ns)
            if infNFe is None:
                continue

            ide = infNFe.find("ns:ide", ns)
            emit = infNFe.find("ns:emit", ns)
            dest = infNFe.find("ns:dest", ns)
            produtos = infNFe.findall(".//ns:det", ns)

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
                        for tag_xml, nome_coluna in campos.items():
                            valor = obter_valor(ns, tag_xml, contexto)
                            linha[nome_coluna] = aplicar_tipo(valor, nome_coluna, formato)

                # Classificação de tipo da nota
                cfop = linha.get("CFOP", "")
                cnpj_emit = linha.get("Emitente CNPJ", "")
                cnpj_dest = linha.get("Destinatário CNPJ", "")
                tipo = "Entrada" if cfop.startswith("1") or cfop.startswith("2") or cnpj_emit == cnpj_dest else "Saída"
                linha["Tipo"] = tipo

                if tipo == "Entrada":
                    entradas.append(linha)
                else:
                    saidas.append(linha)
        except Exception as e:
            print(f"Erro ao processar {caminho}: {e}")

    df_entrada = pd.DataFrame(entradas)
    df_saida = pd.DataFrame(saidas)

    try:
        with open("ordem_colunas.json", "r", encoding="utf-8") as f:
            ordem = json.load(f)["ordem_preferida"]
        if not df_entrada.empty:
            colunas_entrada = [c for c in ordem if c in df_entrada.columns] + [c for c in df_entrada.columns if c not in ordem]
            df_entrada = df_entrada[colunas_entrada]
        if not df_saida.empty:
            colunas_saida = [c for c in ordem if c in df_saida.columns] + [c for c in df_saida.columns if c not in ordem]
            df_saida = df_saida[colunas_saida]
    except Exception as e:
        print("Erro ao reordenar colunas:", e)

    return df_entrada, df_saida
