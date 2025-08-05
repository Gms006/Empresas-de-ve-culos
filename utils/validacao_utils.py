import logging
import pandas as pd

REQUIRED_COLUMNS = [
    "Tipo Nota",
    "Chassi",
    "Placa",
    "CFOP",
    "Valor Total",
    "Data Emissão",
]

log = logging.getLogger(__name__)

def validar_campos_obrigatorios(df: pd.DataFrame) -> None:
    """Verifica existência e preenchimento das colunas obrigatórias.

    Lança ``ValueError`` se alguma coluna estiver ausente ou contiver valores
    nulos/vazios. Mensagens detalhadas são registradas em log.
    """
    missing = [col for col in REQUIRED_COLUMNS if col not in df.columns]
    if missing:
        msg = f"Colunas obrigatórias ausentes: {', '.join(missing)}"
        log.error(msg)
        raise ValueError(msg)

    vazio_cols = []
    for col in REQUIRED_COLUMNS:
        serie = df[col]
        if serie.isna().any() or (serie.astype(str).str.strip() == "").any():
            vazio_cols.append(col)
    if vazio_cols:
        msg = (
            "Valores ausentes nas colunas obrigatórias: "
            + ", ".join(vazio_cols)
        )
        log.error(msg)
        raise ValueError(msg)
