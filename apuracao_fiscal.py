import pandas as pd
from datetime import datetime

# === APURAÇÃO FISCAL TRIMESTRAL ===
def calcular_apuracao(df_estoque):
    df = df_estoque.copy()
    df = df[df["Situação"] == "Vendido"].copy()
    df["Data Saída"] = pd.to_datetime(df["Data Saída"], errors="coerce")

    # Agrupar por trimestre
    df["Trimestre"] = df["Data Saída"].dt.to_period("Q").astype(str)

    # Cálculo de tributos
    df["ICMS Presumido"] = df["Lucro"] * 0.19
    df["PIS/COFINS Presumido"] = df["Lucro"] * 0.0365
    df["Base IRPJ/CSLL"] = df["Lucro"] * 0.32
    df["IRPJ"] = df["Base IRPJ/CSLL"] * 0.15
    df["Adicional IRPJ"] = df["Base IRPJ/CSLL"].apply(lambda x: (x - 60000) * 0.10 if x > 60000 else 0.0)
    df["CSLL"] = df["Base IRPJ/CSLL"] * 0.09
    df["Total Tributos"] = df["ICMS Presumido"] + df["PIS/COFINS Presumido"] + df["IRPJ"] + df["Adicional IRPJ"] + df["CSLL"]
    df["Lucro Líquido"] = df["Lucro"] - df["Total Tributos"]

    resumo = df.groupby("Trimestre").agg({
        "Lucro": "sum",
        "ICMS Presumido": "sum",
        "PIS/COFINS Presumido": "sum",
        "Base IRPJ/CSLL": "sum",
        "IRPJ": "sum",
        "Adicional IRPJ": "sum",
        "CSLL": "sum",
        "Total Tributos": "sum",
        "Lucro Líquido": "sum"
    }).reset_index()

    return resumo, df
