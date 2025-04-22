
import pandas as pd

def calcular_apuracao(df_estoque):
    df = df_estoque.copy()
    df = df[df["Situação"] == "Vendido"].copy()
    df["Data Saída"] = pd.to_datetime(df["Data Saída"], errors="coerce")
    df["Trimestre"] = df["Data Saída"].dt.to_period("Q").astype(str)

    # Calcular tributos por veículo (sem adicional IRPJ)
    df["ICMS Presumido"] = df["Lucro"] * 0.19
    df["PIS/COFINS Presumido"] = df["Lucro"] * 0.0365
    df["Base IRPJ/CSLL"] = df["Lucro"] * 0.32
    df["IRPJ"] = df["Base IRPJ/CSLL"] * 0.15
    df["CSLL"] = df["Base IRPJ/CSLL"] * 0.09
    df["Adicional IRPJ"] = 0.0
    df["Total Tributos"] = df["ICMS Presumido"] + df["PIS/COFINS Presumido"] + df["IRPJ"] + df["CSLL"]
    df["Lucro Líquido"] = df["Lucro"] - df["Total Tributos"]

    # Agrupar por trimestre e somar
    agrupado = df.groupby("Trimestre").agg({
        "Lucro": "sum",
        "ICMS Presumido": "sum",
        "PIS/COFINS Presumido": "sum",
        "Base IRPJ/CSLL": "sum",
        "IRPJ": "sum",
        "CSLL": "sum",
        "Total Tributos": "sum",
        "Lucro Líquido": "sum"
    }).reset_index()

    # Calcular adicional IRPJ após o agrupamento
    adicional_irpj = []
    for _, row in agrupado.iterrows():
        base = row["Base IRPJ/CSLL"]
        adicional = (base - 60000) * 0.10 if base > 60000 else 0.0
        adicional_irpj.append(adicional)

    agrupado["Adicional IRPJ"] = adicional_irpj
    agrupado["Total Tributos"] += agrupado["Adicional IRPJ"]
    agrupado["Lucro Líquido"] -= agrupado["Adicional IRPJ"]

    agrupado = agrupado[[
        "Trimestre", "Lucro", "ICMS Presumido", "PIS/COFINS Presumido",
        "Base IRPJ/CSLL", "IRPJ", "Adicional IRPJ", "CSLL",
        "Total Tributos", "Lucro Líquido"
    ]]

    return agrupado, df.drop(columns=[col for col in df.columns if col.startswith("Unnamed")], errors='ignore')
