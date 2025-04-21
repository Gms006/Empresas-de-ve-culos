# extrator.py (refatorado para uso com Streamlit, modularizado e pronto para GitHub)

import os
import re
import xml.etree.ElementTree as ET
from datetime import datetime
import pandas as pd

cfop_reentrada = {"1102", "1202", "2102"}

# === Utilitários ===
def format_brl(value):
    return f"{float(value):,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")

def format_brl_float(value):
    return float(str(value).replace(".", "").replace(",", "."))

def extrair_placa_chassi(texto):
    placa = chassi = ""
    if texto:
        placa_match = re.search(r"PLACA\s*[:\-]?\s*([A-Z]{3}[0-9A-Z]{4})", texto, re.IGNORECASE)
        chassi_match = re.search(r"CHASSI\s*[:\-]?\s*([A-Z0-9]{8,})", texto, re.IGNORECASE)
        if placa_match:
            placa = placa_match.group(1)
        if chassi_match:
            chassi = chassi_match.group(1)
    return placa, chassi

def extrair_dados_xml(path, tipo):
    try:
        tree = ET.parse(path)
        root = tree.getroot()
        ns = {'ns': 'http://www.portalfiscal.inf.br/nfe'}
        infNFe = root.find(".//ns:infNFe", ns)

        data_emissao = datetime.strptime(infNFe.find("./ns:ide/ns:dhEmi", ns).text[:10], "%Y-%m-%d").strftime("%d/%m/%Y")
        destinatario = infNFe.find("./ns:dest/ns:xNome", ns).text
        numero_nf = infNFe.find("./ns:ide/ns:nNF", ns).text
        cfop = infNFe.find(".//ns:det/ns:prod/ns:CFOP", ns).text
        produto = infNFe.find(".//ns:det/ns:prod/ns:xProd", ns).text
        valor_produto = infNFe.find(".//ns:det/ns:prod/ns:vProd", ns).text
        valor_total = infNFe.find(".//ns:total/ns:ICMSTot/ns:vNF", ns).text

        inf_ad_prod = infNFe.find(".//ns:det/ns:infAdProd", ns)
        texto_inf_ad = inf_ad_prod.text if inf_ad_prod is not None else ""
        texto_comb = f"{produto} ; {texto_inf_ad}"

        placa, chassi = extrair_placa_chassi(texto_comb)

        destino_final = "Entrada" if (tipo == "Entrada" or cfop in cfop_reentrada) else "Saida"

        return {
            "Data": data_emissao,
            "Destinatario": destinatario,
            "Nota Fiscal": numero_nf,
            "Produto": produto,
            "Valor Produto": format_brl(valor_produto),
            "Valor Total": format_brl(valor_total),
            "Valor Total Float": float(valor_total),
            "CFOP": cfop,
            "Placa": placa,
            "Chassi": chassi,
            "Tipo": destino_final
        }

    except Exception as e:
        return None

def gerar_estoque_fiscal(df_entrada, df_saida):
    estoque = []
    entradas = df_entrada.to_dict("records")
    saidas = df_saida.to_dict("records")

    for ent in entradas:
        chave = ent["Chassi"] or ent["Placa"]
        saida_match = next((s for s in saidas if (s["Chassi"] or s["Placa"]) == chave), None)
        item = {
            "Produto": ent["Produto"],
            "Chassi": ent["Chassi"],
            "Placa": ent["Placa"],
            "NF Entrada": ent["Nota Fiscal"],
            "Data Entrada": ent["Data"],
            "Valor Entrada": ent["Valor Total"],
            "NF Saída": saida_match["Nota Fiscal"] if saida_match else "",
            "Data Saída": saida_match["Data"] if saida_match else "",
            "Valor Venda": saida_match["Valor Total"] if saida_match else "",
            "Lucro": (
                format_brl(float(saida_match["Valor Total Float"]) - float(ent["Valor Total Float"]))
                if saida_match else ""
            ),
            "Situação": "Vendido" if saida_match else "Em Estoque"
        }
        estoque.append(item)
    return pd.DataFrame(estoque)

def processar_arquivos_xml(lista_de_caminhos):
    entradas, saidas = [], []

    for caminho in lista_de_caminhos:
        tipo = "Entrada" if "entrada" in caminho.lower() else "Saida"
        dados = extrair_dados_xml(caminho, tipo)
        if dados:
            if dados["Tipo"] == "Entrada":
                entradas.append(dados)
            else:
                saidas.append(dados)

    df_entrada = pd.DataFrame(entradas)
    df_saida = pd.DataFrame(saidas)
    df_estoque = gerar_estoque_fiscal(df_entrada, df_saida)

    return df_entrada, df_saida, df_estoque
