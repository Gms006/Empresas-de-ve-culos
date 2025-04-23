import pandas as pd

def calcular_apuracao(df_estoque):
    df = df_estoque.copy()

    # Filtrar apenas veículos vendidos
    df = df[df["Situação"] == "Vendido"].copy()

    # Garantir que a coluna de data está correta
    df["Data Saída"] = pd.to_datetime(df["Data Saída"], errors="coerce")

    # Definir o trimestre da venda
    df["Trimestre"] = df["Data Saída"].dt.to_period("Q").dt.start_time

    # Garantir que a coluna Lucro é numérica
    df["Lucro"] = pd.to_numeric(df["Lucro"], errors='coerce').fillna(0)

    # Cálculo dos tributos
    df["ICMS Presumido"] = df["Lucro"] * 0.19
    df["PIS/COFINS Presumido"] = df["Lucro"] * 0.0365
    df["Base IRPJ/CSLL"] = df["Lucro"] * 0.32
    df["IRPJ"] = df["Base IRPJ/CSLL"] * 0.15
    df["CSLL"] = df["Base IRPJ/CSLL"] * 0.09
    df["Adicional IRPJ"] = 0.0
    df["Total Tributos"] = df["ICMS Presumido"] + df["PIS/COFINS Presumido"] + df["IRPJ"] + df["CSLL"]
    df["Lucro Líquido"] = df["Lucro"] - df["Total Tributos"]

    # Agrupar por Trimestre
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

    # Cálculo do Adicional IRPJ por Trimestre
    agrupado["Adicional IRPJ"] = agrupado["Base IRPJ/CSLL"].apply(lambda base: (base - 60000) * 0.10 if base > 60000 else 0.0)

    # Atualizar totais após adicional
    agrupado["Total Tributos"] += agrupado["Adicional IRPJ"]
    agrupado["Lucro Líquido"] -= agrupado["Adicional IRPJ"]

    # Reordenar colunas
    agrupado = agrupado[[
        "Trimestre", "Lucro", "ICMS Presumido", "PIS/COFINS Presumido",
        "Base IRPJ/CSLL", "IRPJ", "Adicional IRPJ", "CSLL",
        "Total Tributos", "Lucro Líquido"
    ]]

    # Limpeza de colunas auxiliares
    df = df.drop(columns=[col for col in df.columns if col.startswith("Unnamed")], errors="ignore")

    return agrupado, df
