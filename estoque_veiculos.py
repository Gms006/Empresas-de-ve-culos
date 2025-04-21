# extrator.py - Extrator genérico e robusto de XMLs NF-e

import os
import re
import xml.etree.ElementTree as ET
from datetime import datetime
import pandas as pd

# Expressões regulares para dados livres
regex_map = {
    "chassi": r"CHASSI\s*[:\-]?\s*([A-Z0-9]{8,})",
    "placa": r"PLACA\s*[:\-]?\s*([A-Z]{3}[0-9A-Z]{4})",
    "renavam": r"RENAVAM\s*[:\-]?\s*(\d{9,})",
    "ano_modelo": r"(\d{4})/\d{4}",
    "ano_fabricacao": r"\d{4}/(\d{4})",
    "cor": r"COR\s*[:\-]?\s*([A-Z\s]+)",
    "km": r"KM\s*[:\-]?\s*(\d+)"
}

# === Função principal ===
def processar_arquivos_xml(lista_de_caminhos):
    entradas, saidas = [], []

    for caminho in lista_de_caminhos:
        try:
            tree = ET.parse(caminho)
            root = tree.getroot()
            ns = {'ns': 'http://www.portalfiscal.inf.br/nfe'}
            infNFe = root.find(".//ns:infNFe", ns)

            tipo_nf = infNFe.find(".//ns:ide/ns:tpNF", ns).text
            tipo = "Entrada" if tipo_nf == "0" else "Saida"

            data_emissao = infNFe.find(".//ns:ide/ns:dhEmi", ns).text[:10]
            data_emissao = datetime.strptime(data_emissao, "%Y-%m-%d").strftime("%d/%m/%Y")

            emit = infNFe.find(".//ns:emit", ns)
            dest = infNFe.find(".//ns:dest", ns)
            produtos = infNFe.findall(".//ns:det", ns)

            for det in produtos:
                prod = det.find("ns:prod", ns)
                imposto = det.find("ns:imposto", ns)
                infAdProd = det.find("ns:infAdProd", ns)
                texto_livre = infAdProd.text if infAdProd is not None else ""
                texto_completo = f"{prod.find('ns:xProd', ns).text or ''} {texto_livre}".upper()

                campos_extras = {
                    campo: re.search(regex, texto_completo).group(1)
                    if re.search(regex, texto_completo) else ""
                    for campo, regex in regex_map.items()
                }

                linha = {
                    "Tipo": tipo,
                    "Data Emissão": data_emissao,
                    "Nota Fiscal": infNFe.find(".//ns:ide/ns:nNF", ns).text,
                    "Série": infNFe.find(".//ns:ide/ns:serie", ns).text,
                    "CFOP": prod.find("ns:CFOP", ns).text,
                    "Produto": prod.find("ns:xProd", ns).text,
                    "Código Produto": prod.find("ns:cProd", ns).text,
                    "Quantidade": prod.find("ns:qCom", ns).text,
                    "Valor Unitário": prod.find("ns:vUnCom", ns).text,
                    "Valor Total": prod.find("ns:vProd", ns).text,
                    "Emitente CNPJ": emit.find("ns:CNPJ", ns).text if emit.find("ns:CNPJ", ns) is not None else '',
                    "Emitente Nome": emit.find("ns:xNome", ns).text,
                    "Destinatário CNPJ": dest.find("ns:CNPJ", ns).text if dest.find("ns:CNPJ", ns) is not None else '',
                    "Destinatário Nome": dest.find("ns:xNome", ns).text,
                    "Texto Descritivo": texto_completo,
                    "Chassi": campos_extras["chassi"],
                    "Placa": campos_extras["placa"],
                    "Renavam": campos_extras["renavam"],
                    "Ano Modelo": campos_extras["ano_modelo"],
                    "Ano Fabricação": campos_extras["ano_fabricacao"],
                    "Cor": campos_extras["cor"],
                    "KM": campos_extras["km"]
                }

                if tipo == "Entrada":
                    entradas.append(linha)
                else:
                    saidas.append(linha)

        except Exception as e:
            print(f"Erro ao processar {caminho}: {e}")

    return pd.DataFrame(entradas), pd.DataFrame(saidas)
