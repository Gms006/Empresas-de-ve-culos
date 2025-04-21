
# estoque_veiculos.py - Extrator especializado para empresas de veículos

import os
import re
import json
import xml.etree.ElementTree as ET
from datetime import datetime
import pandas as pd

# Expressões regulares otimizadas para descrição de veículos
regex_map = {
    "chassi": r"(?i)CHASSI[\s.:\\-]*([A-Z0-9]{8,})",
    "placa": r"(?i)PLACA[\s.:\\-]*([A-Z]{3}[0-9A-Z]{4})",
    "renavam": r"(?i)RENAVAM[\s.:\\-]*([0-9]{9,})",
    "ano_modelo": r"(?i)ANO(?:\\s+)?MOD(?:ELO)?[:\\s]*([0-9]{4})",
    "ano_fabricacao": r"(?i)ANO(?:\\s+)?FAB(?:RICACAO)?[:\\s]*([0-9]{4})",
    "cor": r"(?i)COR[\s.:\\-]*([A-Z\\s]+)",
    "km": r"(?i)(?:KM|QUILOMETRAGEM)[\\s.:\\-]*([0-9]{1,7})"
}

# Carrega config de empresas
with open("empresas_config.json", "r", encoding="utf-8") as f:
    config = json.load(f)

empresa_id = list(config.keys())[0]
empresa_info = config[empresa_id]
nomes_proprios = [n.upper() for n in empresa_info["nomes_proprios"]]

# === Função principal ===
def processar_arquivos_xml(lista_de_caminhos):
    entradas, saidas = [], []

    for caminho in lista_de_caminhos:
        try:
            tree = ET.parse(caminho)
            root = tree.getroot()
            ns = {'ns': 'http://www.portalfiscal.inf.br/nfe'}
            infNFe = root.find(".//ns:infNFe", ns)

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

                cnpj_emitente = emit.find("ns:CNPJ", ns).text if emit.find("ns:CNPJ", ns) is not None else ""
                nome_destinatario = dest.find("ns:xNome", ns).text if dest.find("ns:xNome", ns) is not None else ""
                cfop = prod.find("ns:CFOP", ns).text

                # Correção da lógica de tipo
                if cfop.startswith("1") or cfop.startswith("2"):
                    tipo = "Entrada"
                elif any(nome in nome_destinatario.upper() for nome in nomes_proprios):
                    tipo = "Entrada"
                else:
                    tipo = "Saida"

                data_emissao = infNFe.find(".//ns:ide/ns:dhEmi", ns).text[:10]
                data_emissao = datetime.strptime(data_emissao, "%Y-%m-%d").strftime("%d/%m/%Y")

                linha = {
                    "Tipo": tipo,
                    "Data Emissão": data_emissao,
                    "Nota Fiscal": infNFe.find(".//ns:ide/ns:nNF", ns).text,
                    "Série": infNFe.find(".//ns:ide/ns:serie", ns).text,
                    "CFOP": cfop,
                    "Produto": prod.find("ns:xProd", ns).text,
                    "Código Produto": prod.find("ns:cProd", ns).text,
                    "Quantidade": prod.find("ns:qCom", ns).text,
                    "Valor Unitário": prod.find("ns:vUnCom", ns).text,
                    "Valor Total": prod.find("ns:vProd", ns).text,
                    "Emitente CNPJ": cnpj_emitente,
                    "Emitente Nome": emit.find("ns:xNome", ns).text,
                    "Destinatário CNPJ": dest.find("ns:CNPJ", ns).text if dest.find("ns:CNPJ", ns) is not None else '',
                    "Destinatário Nome": nome_destinatario,
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
