
# estoque_veiculos.py - Extrator com fallback de chassi e leitura de regex via JSON

import os
import re
import json
import xml.etree.ElementTree as ET
from datetime import datetime
import pandas as pd

# Carrega regex externo (regex_config.json)
with open("regex_veiculos.json", "r", encoding="utf-8") as r:
    regex_map = json.load(r)

# Carrega config de empresas
with open("empresas_config.json", "r", encoding="utf-8") as f:
    config = json.load(f)

empresa_id = list(config.keys())[0]
empresa_info = config[empresa_id]
nomes_proprios = [n.upper() for n in empresa_info["nomes_proprios"]]


# === Função principal aprimorada com tributos e validações ===
def formatar_cnpj(cnpj):
    if not cnpj or not cnpj.isdigit() or len(cnpj) != 14:
        return cnpj
    return f"{cnpj[:2]}.{cnpj[2:5]}.{cnpj[5:8]}/{cnpj[8:12]}-{cnpj[12:]}"

def formatar_valor(valor):
    try:
        return round(float(valor), 2)
    except:
        return 0.0

def formatar_porcentagem(valor):
    try:
        return round(float(valor) * 100, 2)
    except:
        return 0.0

def formatar_inteiro(valor):
    try:
        return int(float(valor))
    except:
        return ""

def obter_valor(ns, tag, contexto):
    campo = contexto.find(f"ns:{tag}", ns)
    return campo.text if campo is not None else ""

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

                campos_extras = {}
                for campo, padroes in regex_map.items():
                    campos_extras[campo] = ""
                    for padrao in padroes:
                        match = re.search(padrao, texto_completo)
                        if match:
                            campos_extras[campo] = match.group(1)
                            break

                # Fallback: chassi genérico de 17 caracteres
                if not campos_extras["chassi"]:
                    match_chassi_livre = re.search(r"(?<![A-Z0-9])[A-HJ-NPR-Z0-9]{17}(?![A-Z0-9])", texto_completo)
                    if match_chassi_livre:
                        campos_extras["chassi"] = match_chassi_livre.group(0)

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

                imposto_icms = imposto.find(".//ns:ICMS", ns)
                icms_valor = obter_valor(ns, "vICMS", imposto_icms)
                icms_aliq = obter_valor(ns, "pICMS", imposto_icms)
                icms_cst = obter_valor(ns, "CST", imposto_icms)
                icms_csosn = obter_valor(ns, "CSOSN", imposto_icms)
                icms_bc = obter_valor(ns, "vBC", imposto_icms)

                imposto_pis = imposto.find(".//ns:PIS", ns)
                pis_valor = obter_valor(ns, "vPIS", imposto_pis)
                pis_aliq = obter_valor(ns, "pPIS", imposto_pis)

                imposto_cofins = imposto.find(".//ns:COFINS", ns)
                cofins_valor = obter_valor(ns, "vCOFINS", imposto_cofins)
                cofins_aliq = obter_valor(ns, "pCOFINS", imposto_cofins)

                ncm = obter_valor(ns, "NCM", prod)

                cfop_valido = cfop in ["1101", "1102", "5101", "5102", "6101", "6102", "5551"]
                tipo_operacao = "Revenda" if cfop_valido else "Outro"

                linha = {
                    "Tipo": tipo,
                    "Data Emissão": data_emissao,
                    "Nota Fiscal": infNFe.find(".//ns:ide/ns:nNF", ns).text,
                    "Série": infNFe.find(".//ns:ide/ns:serie", ns).text,
                    "CFOP": cfop,
                    "CFOP Válido?": "Sim" if cfop_valido else "Não",
                    "Tipo Operação Fiscal": tipo_operacao,
                    "Produto": prod.find("ns:xProd", ns).text,
                    "Código Produto": prod.find("ns:cProd", ns).text,
                    "NCM": ncm,
                    "Quantidade": formatar_inteiro(prod.find("ns:qCom", ns).text),
                    "Valor Unitário": formatar_valor(prod.find("ns:vUnCom", ns).text),
                    "Valor Total": formatar_valor(prod.find("ns:vProd", ns).text),
                    "Emitente CNPJ": formatar_cnpj(cnpj_emitente),
                    "Emitente Nome": emit.find("ns:xNome", ns).text,
                    "Destinatário CNPJ": formatar_cnpj(dest.find("ns:CNPJ", ns).text) if dest.find("ns:CNPJ", ns) is not None else '',
                    "Destinatário Nome": nome_destinatario,
                    "Texto Descritivo": texto_completo,
                    "Chassi": campos_extras["chassi"],
                    "Placa": campos_extras["placa"],
                    "Renavam": campos_extras["renavam"],
                    "Ano Modelo": formatar_inteiro(campos_extras["ano_modelo"]),
                    "Ano Fabricação": formatar_inteiro(campos_extras["ano_fabricacao"]),
                    "Cor": campos_extras["cor"],
                    "KM": formatar_inteiro(campos_extras["km"]),
                    "ICMS Valor (R$)": formatar_valor(icms_valor),
                    "ICMS Alíquota (%)": formatar_porcentagem(icms_aliq),
                    "ICMS CST": icms_cst,
                    "ICMS CSOSN": icms_csosn,
                    "ICMS Base Cálculo": formatar_valor(icms_bc),
                    "PIS Valor (R$)": formatar_valor(pis_valor),
                    "PIS Alíquota (%)": formatar_porcentagem(pis_aliq),
                    "COFINS Valor (R$)": formatar_valor(cofins_valor),
                    "COFINS Alíquota (%)": formatar_porcentagem(cofins_aliq)
                }
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
