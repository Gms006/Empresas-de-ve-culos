
import pandas as pd
import re
import json
from datetime import datetime

# === Validação por JSON ===
with open("validador_veiculo.json", "r", encoding="utf-8") as f:
    validadores = json.load(f)

def validar_chassi(chassi):
    padrao = validadores.get("chassi")
    return isinstance(chassi, str) and bool(re.match(padrao, chassi))

def validar_placa(placa):
    padrao1 = validadores.get("placa_mercosul")
    padrao2 = validadores.get("placa_antiga")
    return isinstance(placa, str) and (re.match(padrao1, placa) or re.match(padrao2, placa))

# === Classificação por JSON ===
with open("classificacao_produto.json", "r", encoding="utf-8") as f:
    classificacao = json.load(f)

veiculo_keywords = classificacao.get("veiculo_keywords", [])
blacklist = classificacao.get("blacklist", [])

def classificar_produto_linha(row):
    chassi = row.get("Chassi", "")
    placa = row.get("Placa", "")
    produto = str(row.get("Produto", "")).upper()

    if any(palavra in produto for palavra in blacklist):
        return "Outro Produto"
    if validar_chassi(chassi) or validar_placa(placa):
        return "Veículo"
    if any(palavra in produto for palavra in veiculo_keywords):
        return "Veículo"
    return "Outro Produto"

# === Estoque Fiscal ===
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

        item = {
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

# === Auditoria ===
def gerar_alertas_auditoria(df_entrada, df_saida):
    df_entrada["Tipo Produto"] = df_entrada.apply(classificar_produto_linha, axis=1)
    df_saida["Tipo Produto"] = df_saida.apply(classificar_produto_linha, axis=1)

    df_entrada = df_entrada[df_entrada["Tipo Produto"] == "Veículo"]
    df_saida = df_saida[df_saida["Tipo Produto"] == "Veículo"]

    alertas = []

    def obter_chave(df):
        if "Chassi" in df.columns and "Placa" in df.columns:
            return df["Chassi"].fillna(df["Placa"])
        elif "Chassi" in df.columns:
            return df["Chassi"]
        elif "Placa" in df.columns:
            return df["Placa"]
        else:
            return pd.Series([""] * len(df))

    for tipo, df in [("Entrada", df_entrada), ("Saída", df_saida)]:
        chave = obter_chave(df)
        duplicados = df[chave.notna()].groupby(chave).filter(lambda x: len(x) > 1)

        for _, grupo in duplicados.groupby(obter_chave(duplicados)):
            chave_valor = grupo["Chassi"].iloc[0] if "Chassi" in grupo.columns and pd.notna(grupo["Chassi"].iloc[0]) else grupo["Placa"].iloc[0]
            alertas.append({
                "Tipo": tipo,
                "Erro": "Duplicidade",
                "Categoria": "Erro Crítico",
                "Chassi/Placa": chave_valor,
                "Notas": ", ".join(grupo["Nota Fiscal"].astype(str))
            })

    chaves_entrada = set(obter_chave(df_entrada))
    for _, s in df_saida.iterrows():
        chave = s.get("Chassi") or s.get("Placa")
        if chave and chave not in chaves_entrada:
            alertas.append({
                "Tipo": "Saída",
                "Erro": "Saída sem entrada",
                "Categoria": "Erro Crítico",
                "Chassi/Placa": chave,
                "Notas": s.get("Nota Fiscal")
            })

    chaves_saida = set(obter_chave(df_saida))
    for _, e in df_entrada.iterrows():
        chave = e.get("Chassi") or e.get("Placa")
        if chave and chave not in chaves_saida:
            alertas.append({
                "Tipo": "Entrada",
                "Erro": "Entrada sem correspondente saída",
                "Categoria": "Erro Informativo",
                "Chassi/Placa": chave,
                "Notas": e.get("Nota Fiscal")
            })

    return pd.DataFrame(alertas)

# === KPIs ===
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

# === Resumo Mensal ===
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
