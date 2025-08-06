import pandas as pd
from typing import Dict, Optional

# Colunas finais do relatório
COLUMNS = [
    "CPF/CNPJ", "Razão Social", "UF", "Município", "Endereço",
    "Número Documento", "Série", "Data", "Situação", "Acumulador",
    "CFOP", "Valor Produtos", "Valor Descontos", "Valor Contábil",
    "Base de Calculo ICMS", "Alíquota ICMS", "Valor ICMS", "Outras ICMS",
    "Isentas ICMS", "Base de Calculo IPI", "Alíquota IPI", "Valor IPI",
    "Outras IPI", "Isentas IPI", "Código do Item", "Quantidade",
    "Valor Unitário", "CST PIS/COFINS", "Base de Calculo PIS/COFINS",
    "Alíquota PIS", "Valor PIS", "Alíquota COFINS", "Valor COFINS",
]

def gerar_relatorio_fiscal_excel(
    df_notas: pd.DataFrame,
    caminho_saida: str,
    codigo_por_chassi: Optional[Dict[str, str]] = None,
) -> pd.DataFrame:
    """Gera planilha de apuração fiscal a partir de notas de veículos.

    Parameters
    ----------
    df_notas : pd.DataFrame
        DataFrame com as informações das notas fiscais.
    caminho_saida : str
        Caminho do arquivo ``.xlsx`` a ser gerado.
    codigo_por_chassi : Optional[Dict[str, str]], optional
        Mapeamento do chassi do veículo para o código da nota de entrada.
        Se fornecido e existir a coluna ``Chassi`` no DataFrame, o campo
        ``Código do Item`` será preenchido a partir desse mapeamento.

    Returns
    -------
    pd.DataFrame
        DataFrame resultante com as colunas calculadas e ordenadas.
    """
    df = df_notas.copy()

    # Garantir que Valor Contábil corresponde ao Valor Produtos
    df["Valor Contábil"] = df["Valor Produtos"]

    # Cálculo do ICMS
    df["Base de Calculo ICMS"] = df["Valor Produtos"] * 0.05
    df["Alíquota ICMS"] = 0.19
    df["Valor ICMS"] = df["Base de Calculo ICMS"] * df["Alíquota ICMS"]

    # Base de cálculo do PIS/COFINS a partir do lucro
    if "Lucro" in df.columns:
        df["Base de Calculo PIS/COFINS"] = df["Lucro"].fillna(0)
    else:
        df["Base de Calculo PIS/COFINS"] = 0.0

    df["Alíquota PIS"] = 0.0065
    df["Valor PIS"] = df["Base de Calculo PIS/COFINS"] * df["Alíquota PIS"]
    df["Alíquota COFINS"] = 0.03
    df["Valor COFINS"] = df["Base de Calculo PIS/COFINS"] * df["Alíquota COFINS"]

    # Campos constantes
    df["Acumulador"] = 3

    # Preencher campos opcionais com zero se ausentes
    for coluna in [
        "Valor Descontos", "Outras ICMS", "Isentas ICMS", "Base de Calculo IPI",
        "Alíquota IPI", "Valor IPI", "Outras IPI", "Isentas IPI",
        "Quantidade", "Valor Unitário", "CST PIS/COFINS",
    ]:
        if coluna not in df.columns:
            df[coluna] = 0 if coluna not in {"CST PIS/COFINS"} else ""

    if "Valor Unitário" in df.columns:
        df["Valor Unitário"] = df["Valor Unitário"].fillna(df["Valor Produtos"])
    else:
        df["Valor Unitário"] = df["Valor Produtos"]

    if "Quantidade" in df.columns:
        df["Quantidade"] = df["Quantidade"].fillna(1)
    else:
        df["Quantidade"] = 1

    # Código do item mapeado pelo chassi
    if codigo_por_chassi is not None and "Chassi" in df.columns:
        df["Código do Item"] = df["Chassi"].map(codigo_por_chassi)
    elif "Código do Item" not in df.columns:
        df["Código do Item"] = None

    # Ordenar colunas conforme especificação
    for col in COLUMNS:
        if col not in df.columns:
            df[col] = None
    df = df[COLUMNS]

    # Exportar para Excel
    df.to_excel(caminho_saida, index=False)

    return df
