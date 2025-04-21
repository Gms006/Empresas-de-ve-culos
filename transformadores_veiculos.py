
import re

def validar_chassi(chassi):
    return isinstance(chassi, str) and bool(re.match(r"^[A-HJ-NPR-Z0-9]{17}$", chassi))

def validar_placa(placa):
    return isinstance(placa, str) and (
        bool(re.match(r"^[A-Z]{3}[0-9]{4}$", placa)) or
        bool(re.match(r"^[A-Z]{3}[0-9][A-Z][0-9]{2}$", placa))
    )

# transformadores_veiculos.py

import pandas as pd
from datetime import datetime

# === Classificação de Produto ===

def classificar_produto_linha(row):
    chassi = row.get("Chassi", "")
    placa = row.get("Placa", "")
    produto = str(row.get("Produto", "")).upper()

    if validar_chassi(chassi) or validar_placa(placa):
        return "Veículo"
    if any(palavra in produto for palavra in ["VEICULO", "VEÍCULO", "CARRO", "MOTO", "CAMINHÃO"]):
        return "Veículo"
    return "Outro Produto"
# === 1. ESTOQUE FISCAL ===
def gerar_estoque_fiscal(df_entrada, df_saida):
    df_entrada["Tipo Produto"] = df_entrada.apply(classificar_produto_linha, axis=1)
    df_saida["Tipo Produto"] = df_saida.apply(classificar_produto_linha, axis=1)

    df_entrada = df_entrada[df_entrada["Tipo Produto"] == "Veículo"]
    df_saida = df_saida[df_saida["Tipo Produto"] == "Veículo"]

    estoque = []
    entradas = df_entrada.to_dict("records")
    saidas = df_saida.to_dict("records")

    for ent in entradas:
        chave = ent.get("Chassi") or ent.get("Placa")
        saida_match = next((s for s in saidas if (s.get("Chassi") or s.get("Placa")) == chave), None)


        try:
            valor_entrada = float(ent.get("Valor Entrada", 0))
        except:
            valor_entrada = 0.0
        try:
            valor_venda = float(saida_match.get("Valor Total", 0)) if saida_match else 0.0
        except:
            valor_venda = 0.0

        item = {
            "Produto": ent.get("Produto"),
            "Chassi": ent.get("Chassi"),
            "Placa": ent.get("Placa"),
            "Data Entrada": ent.get("Data Emissão"),
            "Valor Entrada": valor_entrada,
            "Data Saída": saida_match.get("Data Emissão") if saida_match else "",
            "Valor Venda": valor_venda,
            "Lucro": valor_venda - valor_entrada,
            "Situação": "Vendido" if saida_match else "Em Estoque",
            "CFOP": ent.get("CFOP"),
            "CFOP Válido?": ent.get("CFOP Válido?"),
            "Tipo Operação Fiscal": ent.get("Tipo Operação Fiscal"),
            "Emitente CNPJ": ent.get("Emitente CNPJ"),
            "Destinatário CNPJ": ent.get("Destinatário CNPJ"),
            "ICMS Valor (R$)": float(ent.get("ICMS Valor (R$)", 0)),
            "ICMS Alíquota (%)": float(ent.get("ICMS Alíquota (%)", 0)),
            "ICMS CST": ent.get("ICMS CST"),
            "ICMS CSOSN": ent.get("ICMS CSOSN"),
            "ICMS Base Cálculo": float(ent.get("ICMS Base Cálculo", 0)),
            "PIS Valor (R$)": float(ent.get("PIS Valor (R$)", 0)),
            "PIS Alíquota (%)": float(ent.get("PIS Alíquota (%)", 0)),
            "COFINS Valor (R$)": float(ent.get("COFINS Valor (R$)", 0)),
            "COFINS Alíquota (%)": float(ent.get("COFINS Alíquota (%)", 0)),
            "NCM": ent.get("NCM"),
            "KM": ent.get("KM"),
            "Ano Modelo": ent.get("Ano Modelo"),
            "Ano Fabricação": ent.get("Ano Fabricação")
        }

            "Produto": ent.get("Produto"),
            "Chassi": ent.get("Chassi"),
            "Placa": ent.get("Placa"),
            "Data Entrada": ent.get("Data Emissão"),
            "Valor Entrada": float(ent.get("Valor Total", 0)),
            "Data Saída": saida_match.get("Data Emissão") if saida_match else "",
            "Valor Venda": float(saida_match.get("Valor Total", 0)) if saida_match else 0.0,
            "Lucro": float(saida_match.get("Valor Total", 0)) - float(ent.get("Valor Total", 0)) if saida_match else 0.0,
            "Situação": "Vendido" if saida_match else "Em Estoque"
        }
        estoque.append(item)

    return pd.DataFrame(estoque)

# === 2. AUDITORIA ===

def gerar_alertas_auditoria(df_entrada, df_saida):
    df_entrada["Tipo Produto"] = df_entrada.apply(classificar_produto_linha, axis=1)
    df_saida["Tipo Produto"] = df_saida.apply(classificar_produto_linha, axis=1)

    df_entrada = df_entrada[df_entrada["Tipo Produto"] == "Veículo"]
    df_saida = df_saida[df_saida["Tipo Produto"] == "Veículo"]

    alertas = []

    def agrupar_validos(df):
        df_validos = df[df["Chassi"].fillna(df["Placa"]).astype(bool)]
        return df_validos.groupby(df_validos["Chassi"].fillna(df_validos["Placa"]))

    # Duplicidade
    for tipo, df in [("Entrada", df_entrada), ("Saída", df_saida)]:
        duplicados = agrupar_validos(df).filter(lambda x: len(x) > 1)
        for _, grupo in duplicados.groupby(duplicados["Chassi"].fillna(duplicados["Placa"])):
            alertas.append({
                "Tipo": tipo,
                "Erro": "Duplicidade",
                "Categoria": "Erro Crítico",
                "Chassi/Placa": grupo["Chassi"].iloc[0] or grupo["Placa"].iloc[0],
                "Notas": ", ".join(grupo["Nota Fiscal"].astype(str))
            })

    # Saída sem entrada
    chaves_entrada = set(df_entrada["Chassi"].fillna(df_entrada["Placa"]))
    for _, s in df_saida.iterrows():
        chave = s["Chassi"] or s["Placa"]
        if chave and chave not in chaves_entrada:
            alertas.append({
                "Tipo": "Saída",
                "Erro": "Saída sem entrada",
                "Categoria": "Erro Crítico",
                "Chassi/Placa": chave,
                "Notas": s["Nota Fiscal"]
            })

    # Entrada sem saída
    chaves_saida = set(df_saida["Chassi"].fillna(df_saida["Placa"]))
    for _, e in df_entrada.iterrows():
        chave = e["Chassi"] or e["Placa"]
        if chave and chave not in chaves_saida:
            alertas.append({
                "Tipo": "Entrada",
                "Erro": "Entrada sem saída",
                "Categoria": "Erro Informativo",
                "Chassi/Placa": chave,
                "Notas": e["Nota Fiscal"]
            })

    # Entrada sem chassi/placa
    for _, e in df_entrada[df_entrada["Chassi"].eq("") & df_entrada["Placa"].eq("")].iterrows():
        alertas.append({
            "Tipo": "Entrada",
            "Erro": "Sem chassi ou placa",
            "Categoria": "Erro Informativo",
            "Chassi/Placa": "",
            "Notas": e["Nota Fiscal"]
        })

    # Saída sem chassi/placa
    for _, s in df_saida[df_saida["Chassi"].eq("") & df_saida["Placa"].eq("")].iterrows():
        alertas.append({
            "Tipo": "Saída",
            "Erro": "Sem chassi ou placa",
            "Categoria": "Erro Informativo",
            "Chassi/Placa": "",
            "Notas": s["Nota Fiscal"]
        })

    return pd.DataFrame(alertas)
def gerar_kpis(df_estoque):
    vendidos = df_estoque[df_estoque["Situação"] == "Vendido"]
    em_estoque = df_estoque[df_estoque["Situação"] == "Em Estoque"]

    return {
        "Total Vendido (R$)": vendidos["Valor Venda"].sum(),
        "Total Comprado (R$)": df_estoque["Valor Entrada"].sum(),
        "Lucro Total (R$)": vendidos["Lucro"].sum(),
        "Estoque Atual (R$)": em_estoque["Valor Entrada"].sum(),
        "Veículos Vendidos": len(vendidos),
        "Veículos em Estoque": len(em_estoque)
    }

# === 4. RESUMO MENSAL ===
def gerar_resumo_mensal(df_estoque):
    df = df_estoque.copy()
    df["Mês"] = pd.to_datetime(df["Data Entrada"], dayfirst=True, errors='coerce').dt.to_period("M")
    resumo = df.groupby("Mês").agg({
        "Valor Entrada": "sum",
        "Valor Venda": "sum",
        "Lucro": "sum",
        "Produto": "count"
    }).rename(columns={"Produto": "Qtd Entradas"}).reset_index()

    return resumo
