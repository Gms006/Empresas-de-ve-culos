import pandas as pd
from typing import Dict, Optional
import xml.etree.ElementTree as ET
import re
import os
import json

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

# Carregar configuração de extração de XML
CONFIG_PATH = os.path.join(os.path.dirname(__file__), "..", "config")
try:
    with open(os.path.join(CONFIG_PATH, "extracao_config.json"), encoding="utf-8") as f:
        CONFIG_EXTRACAO = json.load(f)
except Exception:
    CONFIG_EXTRACAO = {"xpath_campos": {}}


def _formatar_cnpj_cpf(valor: str) -> str:
    """Formata CPF ou CNPJ adicionando máscaras padrão."""
    if not valor:
        return ""
    digitos = re.sub(r"\D", "", valor)
    if len(digitos) == 14:
        return f"{digitos[:2]}.{digitos[2:5]}.{digitos[5:8]}/{digitos[8:12]}-{digitos[12:]}"
    if len(digitos) == 11:
        return f"{digitos[:3]}.{digitos[3:6]}.{digitos[6:9]}-{digitos[9:]}"
    return valor


def _extrair_dados_xml_basicos(xml_path: str) -> Dict[str, str]:
    """Extrai campos básicos necessários para o relatório fiscal de um XML."""
    try:
        tree = ET.parse(xml_path)
        root = tree.getroot()
        ns_match = re.match(r"\{(.+?)\}", root.tag)
        ns = {"nfe": ns_match.group(1)} if ns_match else {}

        def tx(path: Optional[str]) -> str:
            if not path:
                return ""
            return root.findtext(path, namespaces=ns) or ""

        xpath_campos = CONFIG_EXTRACAO.get("xpath_campos", {})

        cnpj = ""
        for key in ("CPF/CNPJ", "Destinatário CNPJ", "Destinatário CPF"):
            cnpj = tx(xpath_campos.get(key))
            if cnpj:
                break
        if not cnpj:
            cnpj = tx(".//nfe:dest/nfe:CNPJ") or tx(".//nfe:dest/nfe:CPF")

        razao = (
            tx(xpath_campos.get("Razão Social"))
            or tx(xpath_campos.get("Destinatário Nome"))
            or tx(".//nfe:dest/nfe:xNome")
        )
        uf = tx(xpath_campos.get("UF")) or tx(".//nfe:dest/nfe:enderDest/nfe:UF")
        municipio = tx(xpath_campos.get("Município")) or tx(
            ".//nfe:dest/nfe:enderDest/nfe:xMun"
        )
        logradouro = tx(xpath_campos.get("Endereço")) or tx(
            ".//nfe:dest/nfe:enderDest/nfe:xLgr"
        )
        numero = tx(xpath_campos.get("Número Endereço")) or tx(
            ".//nfe:dest/nfe:enderDest/nfe:nro"
        )
        endereco = " ".join(filter(None, [logradouro, numero])).strip()

        numero_documento = (
            tx(xpath_campos.get("Número Documento"))
            or tx(xpath_campos.get("Número NF"))
            or tx(".//nfe:ide/nfe:nNF")
        )
        serie = tx(xpath_campos.get("Série")) or tx(".//nfe:ide/nfe:serie")
        data = (
            tx(xpath_campos.get("Data"))
            or tx(xpath_campos.get("Data Emissão"))
            or tx(".//nfe:ide/nfe:dhEmi")
            or tx(".//nfe:ide/nfe:dEmi")
        )
        if data:
            try:
                data = pd.to_datetime(data).date().isoformat()
            except Exception:
                pass
        cfop = tx(xpath_campos.get("CFOP")) or tx(".//nfe:det/nfe:prod/nfe:CFOP")

        return {
            "CPF/CNPJ": _formatar_cnpj_cpf(cnpj),
            "Razão Social": razao,
            "UF": uf,
            "Município": municipio,
            "Endereço": endereco,
            "Número Documento": numero_documento,
            "Série": serie,
            "Data": data,
            "CFOP": cfop,
        }
    except Exception:
        return {}


def _resolver_xml_path(row: pd.Series) -> Optional[str]:
    """Determina a coluna do caminho do XML disponível na linha."""
    for col in ["XML Path", "XML Path_saida", "XML Path_entrada"]:
        path = row.get(col)
        if isinstance(path, str) and path:
            return path
    return None

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

    # Tentar preencher campos essenciais a partir do XML, se ausentes
    campos_xml = [
        "CPF/CNPJ",
        "Razão Social",
        "UF",
        "Município",
        "Endereço",
        "Número Documento",
        "Série",
        "Data",
        "CFOP",
    ]

    for idx, row in df.iterrows():
        if any(not row.get(c) for c in campos_xml):
            xml_path = _resolver_xml_path(row)
            if not xml_path:
                continue
            dados = _extrair_dados_xml_basicos(xml_path)
            for campo in campos_xml:
                valor_atual = row.get(campo)
                if (campo not in df.columns) or (valor_atual in (None, "") or (isinstance(valor_atual, float) and pd.isna(valor_atual))):
                    novo_valor = dados.get(campo)
                    if novo_valor not in (None, ""):
                        df.at[idx, campo] = novo_valor

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
